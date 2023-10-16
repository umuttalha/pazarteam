from flask import Flask, render_template, request, make_response, session, Response
from flask_mail import Mail, Message
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests
import re
import time
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


my_function_lock = threading.Lock()

chrome_driver_path = "./chromedriver"
options = Options()
options.add_argument("--headless")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
)
options.add_argument("--enable-javascript")

load_dotenv()


def my_function():
    with app.app_context():
        with my_function_lock:
            current_utc_time = int(time.time())

            matching_products = Product.query.filter(
                current_utc_time > Product.next_fetch_date
            ).all()

            print(current_utc_time)
            print(matching_products)

            if matching_products ==[]:
                return 
            else:
                for product in matching_products:

                    print(product.level)

                    if product.level==1:
                        response = requests.get(product.product_link, timeout=3)
                        soup = BeautifulSoup(response.content, "html.parser")

                    else:

                        driver = webdriver.Chrome( executable_path=chrome_driver_path, options=options)
                        driver.get(product.product_link)

                        # WebDriverWait(driver, 5).until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), price))
                        time.sleep(2)

                        page_content = driver.page_source

                        driver.quit()

                        soup = BeautifulSoup(page_content, "html.parser")

                        print(soup)


                    python_degisik= product.parent_tag.replace('"', '').replace("'", '')

                    if product.parent_tag in str(soup) or python_degisik in str(soup):

                        product_to_update = Product.query.filter_by(id=product.id).first()

                        if product_to_update:

                            product_to_update.last_fetch_date = int(time.time())
                            product_to_update.next_fetch_date = int(time.time()) + 6 * 3600
                            db.session.commit()

                    else:

                        # change_price_mail(product.user_email, product.product_link, product.title)

                        product_to_delete = Product.query.filter_by(id=product.id).first()

                        if product_to_delete:
                            db.session.delete(product_to_delete)
                            db.session.commit()


app = Flask(__name__, static_folder="static", static_url_path="")
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(my_function, CronTrigger(second="*/30"))
scheduler.start()

mail_settings = {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 465,
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": os.environ["EMAIL_USER"],
    "MAIL_PASSWORD": os.environ["EMAIL_PASSWORD"],
}

app.config.update(mail_settings)
mail = Mail(app)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
db = SQLAlchemy(app)


class User(db.Model):
    email = db.Column(db.String, primary_key=True, unique=True, nullable=False)
    tier = db.Column(db.Integer, nullable=False)
    products = db.relationship("Product", backref="user", lazy=True)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_email = db.Column(db.String, db.ForeignKey("user.email"), nullable=False)
    title = db.Column(db.String, nullable=True)
    price = db.Column(db.String, nullable=False)
    parent_tag = db.Column(db.String, nullable=False)
    product_link = db.Column(db.String, nullable=False, unique=False)
    kota = db.Column(db.Integer)
    level = db.Column(db.Integer)

    first_fetch_date = db.Column(db.Integer, default=int(time.time()), nullable=False)
    last_fetch_date = db.Column(db.Integer, default=int(time.time()), nullable=False)
    next_fetch_date = db.Column(db.Integer, default=int(time.time()) + 6 * 3600, nullable=False)

def add_user(email, tier):
    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        pass
    else:
        new_user = User(email=email, tier=tier)
        db.session.add(new_user)
        db.session.commit()

def add_product(user_email, title, parent_tag, price, product_link,level):
    new_product = Product(
        user_email=user_email,
        parent_tag=parent_tag,
        title=title,
        kota=12,
        price=price,
        product_link=product_link,
        level=level
    )
    db.session.add(new_product)
    db.session.commit()


class_list_names = {"money", "price", "prc-dsc", "fiyat", "amount", "pricing", "prc"}

alert_string = """ 

<div class="alert alert-danger alert-dismissible fade show" role="alert">
    Unsuccessful. The price or link was entered incorrectly, or website has disabled access for this type of work.
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
</div>

"""

alert_string2 = """ 

<div class="alert alert-danger alert-dismissible fade show" role="alert">
    Unsuccessful. Website has disabled access for this type of work.
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
</div>

"""

def change_price_mail(receiver_mail, website_link, title):
    msg = Message(
        subject="Price Changed",
        sender=app.config.get("MAIL_USERNAME"),
        recipients=[receiver_mail],
        body=f"""
    Hi!
                    
    The price of the product ({title} ) you are following has changed. Here is the product link {website_link}
    """,
    )
    mail.send(msg)


def selenium_scrape(url, price):
    elements_check = []
    money_price_elements = []

    driver = webdriver.Chrome(executable_path=chrome_driver_path, options=options)

    driver.get(url)

    WebDriverWait(driver, 5).until(
        EC.text_to_be_present_in_element((By.TAG_NAME, "body"), price)
    )

    page_content = driver.page_source

    driver.quit()

    soup = BeautifulSoup(page_content, "html.parser")

    fiyatlar = soup.find_all(string=re.compile(price))

    for fiyat in fiyatlar:
        parent = fiyat.find_parent()

        if parent and parent.name in {"script", "style"}:
            continue

        elements_check.append({"fiyat": fiyat, "parent": parent})

        parent_classes = set(parent.get("class", []))
        if class_list_names & parent_classes:
            money_price_elements.append({"fiyat": fiyat, "parent": parent})

    try:
        result = money_price_elements[0]
    except:
        try:
            result = elements_check[0]
        except:
            result = ""

    return {
        "result": result,
        "scrap_type": 2,
    }

def check_banned_site(url):
    parsed_url = urlparse(url)

    netloc_parts = parsed_url.netloc.split(".")

    if len(netloc_parts) > 1:
        main_domain = ".".join(netloc_parts[-2:])
    else:
        main_domain = netloc_parts[0]

    if main_domain == "aliexpress.com":
        return "false"
    else:
        return "true"

def verileri_al(url, price):
    try:
        response = requests.get(url, timeout=3)
    except requests.Timeout:
        return selenium_scrape(url, price)
    except requests.RequestException:
        return selenium_scrape(url, price)

    soup = BeautifulSoup(response.content, "html.parser")

    fiyatlar = soup.find_all(string=re.compile(price))
    elements_check = []
    money_price_elements = []

    for fiyat in fiyatlar:
        parent = fiyat.find_parent()

        if parent and parent.name in {"script", "style"}:
            continue

        elements_check.append({"fiyat": fiyat, "parent": parent})

        parent_classes = set(parent.get("class", []))
        if class_list_names & parent_classes:
            money_price_elements.append({"fiyat": fiyat, "parent": parent})

    try:
        result = money_price_elements[0]
    except:
        try:
            result = elements_check[0]
        except:
            return selenium_scrape(url, price)

    return {
        "result": result,
        "scrap_type": 1,
    }


@app.route("/")
def home():
    return render_template("home.html")

@app.route("/process", methods=["POST"])
def process():
    input_data = request.form.get("inputData")

    add_user(input_data, 1)

    products = Product.query.filter_by(user_email=input_data).all()

    response = make_response(
        render_template("products.html", products=products, input_data=input_data)
    )
    response.set_cookie("user_email", input_data)

    return response


@app.route("/deneme", methods=["POST"])
def deneme():
    title = request.form.get("title")
    url = request.form.get("url")
    price = request.form.get("price")

    cevap = check_banned_site(url)

    if cevap == "false":
        return alert_string2

    else:
        user_email = request.cookies.get("user_email")

        elemet_list = verileri_al(url, price)

        if elemet_list["result"] == "":
            return alert_string

        add_product(
            user_email,
            title,
            str(elemet_list["result"]["parent"]),
            elemet_list["result"]["fiyat"],
            url,
            elemet_list["scrap_type"]
        )

        products = Product.query.filter_by(user_email=user_email).all()

        return render_template("accordion.html", products=products,input_data=user_email)

if __name__ == "__main__":
    app.app_context().push()
    db.create_all()
    app.run()
