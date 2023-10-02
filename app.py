from flask import Flask,render_template,request,redirect,make_response,session,jsonify,url_for
from flask_mail import Mail, Message
import os
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from enum import Enum
import secrets
import random
from datetime import timedelta
from urllib.parse import urlparse
import time
from datetime import datetime

from bs4 import BeautifulSoup
from lxml import etree
import requests
import re 

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

chrome_driver_path = './chromedriver'
options = Options()
options.add_argument('--headless')  




load_dotenv()

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = secrets.token_urlsafe(16)
app.permanent_session_lifetime = timedelta(minutes=30)

mail_settings = {
    "MAIL_SERVER": 'smtp.gmail.com',
    "MAIL_PORT": 465,
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": os.environ['EMAIL_USER'],
    "MAIL_PASSWORD": os.environ['EMAIL_PASSWORD']
}


app.config.update(mail_settings)
mail = Mail(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

class TierEnum(Enum):
    FREE = 'Free'
    PREMIUM = 'Premium'

class User(db.Model):
    email = db.Column(db.String, primary_key=True, unique=True, nullable=False)
    tier = db.Column(db.Enum(TierEnum), nullable=False)


class Product(db.Model):
    link = db.Column(db.String, primary_key=True, nullable=False)
    title = db.Column(db.String, nullable=False)
    price = db.Column(db.String, nullable=False)



def change_price_mail(receiver_mail,website_link):

    msg = Message(subject="Price Changed", sender=app.config.get("MAIL_USERNAME"), recipients=[receiver_mail], body=f"""
    Hi!
                    
    The price of the product you are following has changed. Here is the product link {website_link}
    """)
    mail.send(msg)

def generate_client_id():
    return str(random.randint(1, 999999))



def verileri_al(url,price):

    response = requests.get(url)
    
    soup = BeautifulSoup(response.content, 'html.parser')
    
    elements = soup.find_all(string=re.compile(price))

    if elements ==[]:

        driver = webdriver.Chrome(executable_path=chrome_driver_path, options=options)

        driver.get(url)

        page_content = driver.page_source

        driver.quit()

        soup = BeautifulSoup(page_content, 'html.parser')
    
        elements1 = soup.find_all(string=re.compile(price))

        for element in elements1:
            parent = element.find_parent()
            
            if parent and parent.name == 'script' or "style":
                continue
            
            if parent and 'class' in parent.attrs:
                class_list = parent['class']
            else:
                class_list = None

            print(f'Tag: {parent.name if parent else None}, Sınıf: {class_list}, İçerik: {element}')

            return {
                "url": url,
            }

    

    for element in elements:
        parent = element.find_parent()

        
        if parent and parent.name == 'script' or "style":
            continue
        
        if parent and 'class' in parent.attrs:
            class_list = parent['class']
        else:
            class_list = None

        print(f'Tag: {parent.name if parent else None}, Sınıf: {class_list}, İçerik: {element}')


    return {
        "url": url,
        # "urun_title":urun_title,
        # "urun_fiyat": urun_fiyat,
    }




@app.route("/")
def home():
    return render_template("home.html")


@app.route("/process", methods=['POST'])
def process():
    input_data = request.form.get('inputData')

    # Kullanıcıya özgü bir oturum kimliği oluşturun
    session_token = secrets.token_urlsafe(16)

    # Kullanıcı oturum bilgilerini saklayın (örneğin, ürün linki ve input data)
    session[session_token] = {'input_data': input_data}

    return redirect(f'/products/{session_token}')


@app.route('/products/<session_token>')
def products(session_token):
    # Kullanıcının oturumunu kontrol edin
    user_data = session.get(session_token)

    print(user_data)

    if not user_data:
        return redirect('/')

    # Veritabanına kaydetmek istediğiniz bilgileri alın
    input_data = user_data.get('input_data')

    # Burada veritabanına kaydetme işlemlerini yapabilirsiniz (örneğin SQLAlchemy kullanabilirsiniz)

    return render_template('products.html', input_data=input_data)


@app.route("/deneme", methods=['POST'])
def deneme():
    title = request.form.get('title')
    url = request.form.get('url')
    price = request.form.get('price')

    verileri_al(url,price)
    
    client_id = "id"+ generate_client_id()

    return render_template('accordion.html', title=title, url=url,price=price,client_id=client_id)

#     # print(request.__dict__)
    
#     # user_ip = request.remote_addr


if __name__ == "__main__":
    app.app_context().push()
    db.create_all()
    app.run(debug=True) 