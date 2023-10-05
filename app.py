from flask import (
    Flask,
    render_template,
    request,
    redirect,
    make_response,
    session,
    jsonify,
    url_for,
    Response,
)
from flask_mail import Mail, Message
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from enum import Enum
import secrets
import random
from datetime import timedelta, datetime
from urllib.parse import urlparse
import time

from bs4 import BeautifulSoup
from lxml import etree
import requests
import re

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

chrome_driver_path = "./chromedriver"
options = Options()
options.add_argument("--headless")
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
options.add_argument("--enable-javascript")

load_dotenv()

app = Flask(__name__, static_folder="static", static_url_path="")
# app.secret_key = secrets.token_urlsafe(16)
# app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

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


class Product(db.Model):
    link = db.Column(db.String, primary_key=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    price = db.Column(db.String, nullable=False)


class WebsitesLevels(db.Model):
    link = db.Column(db.String,  primary_key=True, nullable=False)
    level = db.Column(db.Integer, nullable=False, default=1) 


class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    link = db.Column(db.String, nullable=False)
    price = db.Column(db.String, nullable=False)


class_list_names = {"money", "price", "prc-dsc", "fiyat", "amount", "pricing", "prc"}

alert_string=""" 

<div class="alert alert-danger alert-dismissible fade show" role="alert">
    Unsuccessful. The price or link was entered incorrectly, or website has disabled access for this type of work.
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
</div>

"""

alert_string2=""" 

<div class="alert alert-danger alert-dismissible fade show" role="alert">
    Unsuccessful. Website has disabled access for this type of work.
    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
</div>

"""

def suanki_tarihi_ve_saati_al():
    suanki_zaman = datetime.now()
    suanki_tarih_ve_saat = suanki_zaman.strftime("%A, %B %d, %Y %H:%M:%S")
    return suanki_tarih_ve_saat

def change_price_mail(receiver_mail, website_link):
    msg = Message(
        subject="Price Changed",
        sender=app.config.get("MAIL_USERNAME"),
        recipients=[receiver_mail],
        body=f"""
    Hi!
                    
    The price of the product you are following has changed. Here is the product link {website_link}
    """,
    )
    mail.send(msg)

def selenium_scrape(url, price):
    elements_check_selenium = []
    parent_list = []
    money_price_elements = []

    driver = webdriver.Chrome(executable_path=chrome_driver_path, options=options)

    driver.get(url)

    # time.sleep(1)
    WebDriverWait(driver, 5).until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), price))

    page_content = driver.page_source

    driver.quit()

    soup = BeautifulSoup(page_content, "html.parser")

    elements1 = soup.find_all(string=re.compile(price))

    for element in elements1:
        parent = element.find_parent()

        if parent and parent.name in {"script", "style"}:
            continue

        elements_check_selenium.append(element)
        parent_list.append(parent)

        parent_classes = set(parent.get("class", []))
        if class_list_names & parent_classes:
            money_price_elements.append(element)

    return {
        "elementler": elements_check_selenium,
        "scrap_type": "level 2",
        "parent_list": parent_list,
        "money_price_elements": money_price_elements,
    }

def verileri_al(url, price):
    try:
        response = requests.get(url, timeout=3)
    except requests.Timeout:
        return selenium_scrape(url, price)
    except requests.RequestException:
        return selenium_scrape(url, price)

    soup = BeautifulSoup(response.content, "html.parser")

    elements = soup.find_all(string=re.compile(price))
    elements_check = []
    parent_list = []
    money_price_elements = []

    for element in elements:
        parent = element.find_parent()

        if parent and parent.name in {"script", "style"}:
            continue

        elements_check.append(element)
        parent_list.append(parent)

        parent_classes = set(parent.get("class", []))
        if class_list_names & parent_classes:
            money_price_elements.append(element)

    if elements_check == []:
        return selenium_scrape(url, price)

    return {
        "elementler": elements_check,
        "scrap_type": "level 1",
        "parent_list": parent_list,
        "money_price_elements": money_price_elements,
    }


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/process", methods=["POST"])
def process():
    input_data = request.form.get("inputData")

    existing_user = User.query.filter_by(email=input_data).first()

    if not existing_user:
        new_user = User(email=input_data, tier=0)
        db.session.add(new_user)
        db.session.commit()

    response = make_response(render_template("products.html", input_data=input_data))
    response.set_cookie("user_email", input_data)

    return response

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




@app.route("/deneme", methods=["POST"])
def deneme():
    title = request.form.get("title")
    url = request.form.get("url")
    price = request.form.get("price")

    cevap = check_banned_site(url)

    if (cevap=="false"):
        return alert_string2
    
    else:
        user_email = request.cookies.get("user_email")

        elemet_list = verileri_al(url, price)

        suanki_tarih_ve_saat = suanki_tarihi_ve_saati_al()

        # print(elemet_list["elementler"])
        # print(elemet_list["parent_list"])

        element_list = { "money_price_elements": (elemet_list["money_price_elements"],), "elementler": (elemet_list["elementler"],),}

        try:
            result = element_list.get("elementler", element_list.get("money_price_elements", [None]))[0][0]
        except:
            return alert_string


        print(result)

        client_id = "id" + str(random.randint(1, 999999))

        if elemet_list["elementler"] == []:
            return alert_string

        return render_template(
            "accordion.html",
            title=title,
            url=url,
            price=price,
            client_id=client_id,
            result=result,
            scrap_type=elemet_list["scrap_type"],
            suanki_tarih_ve_saat=suanki_tarih_ve_saat,
        )


if __name__ == "__main__":
    app.app_context().push()
    db.create_all()
    app.run(debug=True)