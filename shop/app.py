from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import json, os, uuid
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "supersecretkey123"

DB_FILE = "data.json"

CURRENCIES = {
    "RUB": {"symbol": "₽",  "name": "Рубль (RUB)",    "rate": 1.0},
    "MDL": {"symbol": "L",  "name": "Лей (MDL)",       "rate": 0.19},
    "UAH": {"symbol": "₴",  "name": "Гривна (UAH)",    "rate": 0.41},
    "BYN": {"symbol": "Br", "name": "Бел. рубль (BYN)", "rate": 0.033},
}

PAYMENT_METHODS = {
    "RUB": [{"name": "Карта VISA / Mastercard / МИР", "icon": "💳", "detail": "Введите данные карты"}],
    "MDL": [
        {"name": "Карта VISA / Mastercard", "icon": "💳", "detail": "MAIB, Victoriabank, Moldova Agroindbank"},
        {"name": "Перевод на карту",        "icon": "📲", "detail": "Номер карты: 1234 5678 9012 3456"},
    ],
    "UAH": [
        {"name": "Карта VISA / Mastercard", "icon": "💳", "detail": "PrivatBank, Monobank, ПУМБ"},
        {"name": "Monobank / PrivatBank",   "icon": "📲", "detail": "Номер карты: 4149 6090 1234 5678"},
    ],
    "BYN": [
        {"name": "Карта VISA / Mastercard", "icon": "💳", "detail": "Беларусбанк, Альфа-Банк, МТБанк"},
        {"name": "Перевод на карту",        "icon": "📲", "detail": "Номер карты: 9112 3456 7890 1234"},
    ],
}

def convert_price(rub_price, code):
    rate = CURRENCIES.get(code, CURRENCIES["RUB"])["rate"]
    converted = rub_price * rate
    sym = CURRENCIES[code]["symbol"]
    if code == "BYN":
        return f"{converted:.2f} {sym}"
    return f"{int(converted):,}".replace(",", " ") + f" {sym}"

@app.context_processor
def inject_currency():
    code = session.get("currency", "RUB")
    if code not in CURRENCIES:
        code = "RUB"
    def format_price(rub_price):
        return convert_price(rub_price, code)
    return dict(
        current_currency=code,
        currency_symbol=CURRENCIES[code]["symbol"],
        currency_name=CURRENCIES[code]["name"],
        currencies=CURRENCIES,
        format_price=format_price,
        payment_methods=PAYMENT_METHODS.get(code, PAYMENT_METHODS["RUB"]),
    )

@app.route("/set_currency/<code>")
def set_currency(code):
    if code in CURRENCIES:
        session["currency"] = code
    return redirect(request.referrer or url_for("index"))

def load_data():
    if not os.path.exists(DB_FILE):
        default = {
            "products": [
                {"id": "1", "name": "Кожаная куртка",  "price": 12990, "category": "Верхняя одежда", "description": "Классическая кожаная куртка из натуральной кожи.", "image": "jacket.jpg",  "stock": 15, "featured": True},
                {"id": "2", "name": "Джинсы Slim Fit", "price": 4990,  "category": "Брюки",          "description": "Современные джинсы прямого кроя.",                 "image": "jeans.jpg",   "stock": 30, "featured": True},
                {"id": "3", "name": "Белая рубашка",   "price": 2990,  "category": "Рубашки",        "description": "Классическая белая рубашка из 100% хлопка.",       "image": "shirt.jpg",   "stock": 25, "featured": False},
                {"id": "4", "name": "Кроссовки Urban", "price": 7990,  "category": "Обувь",          "description": "Стильные городские кроссовки.",                    "image": "sneakers.jpg","stock": 20, "featured": True},
                {"id": "5", "name": "Шерстяной свитер","price": 5490,  "category": "Свитеры",        "description": "Мягкий свитер из мериносовой шерсти.",             "image": "sweater.jpg", "stock": 18, "featured": False},
                {"id": "6", "name": "Шёлковый шарф",   "price": 1990,  "category": "Аксессуары",     "description": "Элегантный шёлковый шарф с уникальным принтом.",  "image": "scarf.jpg",   "stock": 40, "featured": True},
            ],
            "orders": [],
            "admin": {"username": "admin", "password": "admin123"}
        }
        save_data(default)
        return default
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    data = load_data()
    featured = [p for p in data["products"] if p.get("featured")]
    return render_template("index.html", products=data["products"], featured=featured)

@app.route("/shop")
def shop():
    data = load_data()
    category = request.args.get("category", "")
    products = data["products"]
    if category:
        products = [p for p in products if p["category"] == category]
    categories = sorted(set(p["category"] for p in data["products"]))
    return render_template("shop.html", products=products, categories=categories, selected=category)

@app.route("/product/<pid>")
def product(pid):
    data = load_data()
    prod = next((p for p in data["products"] if p["id"] == pid), None)
    if not prod:
        return redirect(url_for("shop"))
    return render_template("product.html", product=prod)

@app.route("/cart")
def cart():
    cart_data = session.get("cart", {})
    data = load_data()
    items = []
    total_rub = 0
    for pid, qty in cart_data.items():
        prod = next((p for p in data["products"] if p["id"] == pid), None)
        if prod:
            items.append({"product": prod, "qty": qty, "subtotal": prod["price"] * qty})
            total_rub += prod["price"] * qty
    return render_template("cart.html", items=items, total_rub=total_rub)

@app.route("/add_to_cart/<pid>", methods=["POST"])
def add_to_cart(pid):
    cart_data = session.get("cart", {})
    qty = int(request.form.get("qty", 1))
    cart_data[pid] = cart_data.get(pid, 0) + qty
    session["cart"] = cart_data
    flash("Товар добавлен в корзину!", "success")
    return redirect(request.referrer or url_for("shop"))

@app.route("/remove_from_cart/<pid>")
def remove_from_cart(pid):
    cart_data = session.get("cart", {})
    cart_data.pop(pid, None)
    session["cart"] = cart_data
    return redirect(url_for("cart"))

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if request.method == "POST":
        cart_data = session.get("cart", {})
        data = load_data()
        items = []
        total_rub = 0
        for pid, qty in cart_data.items():
            prod = next((p for p in data["products"] if p["id"] == pid), None)
            if prod:
                items.append({"name": prod["name"], "price": prod["price"], "qty": qty})
                total_rub += prod["price"] * qty
        code = session.get("currency", "RUB")
        order = {
            "id": str(uuid.uuid4())[:8].upper(),
            "name": request.form["name"],
            "email": request.form["email"],
            "phone": request.form["phone"],
            "address": request.form["address"],
            "payment": request.form.get("payment", "Карта"),
            "currency": code,
            "total_display": convert_price(total_rub, code),
            "items": items,
            "total": total_rub,
            "status": "Новый",
            "date": datetime.now().strftime("%d.%m.%Y %H:%M")
        }
        data["orders"].append(order)
        save_data(data)
        session["cart"] = {}
        flash(f"Заказ #{order['id']} оформлен! Спасибо!", "success")
        return redirect(url_for("index"))
    cart_data = session.get("cart", {})
    data = load_data()
    total_rub = sum(
        next((p["price"] for p in data["products"] if p["id"] == pid), 0) * qty
        for pid, qty in cart_data.items()
    )
    return render_template("checkout.html", total_rub=total_rub)

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        data = load_data()
        if request.form["username"] == data["admin"]["username"] and \
           request.form["password"] == data["admin"]["password"]:
            session["admin"] = True
            return redirect(url_for("admin_dashboard"))
        flash("Неверные данные!", "error")
    return render_template("admin/login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login"))

@app.route("/admin")
@login_required
def admin_dashboard():
    data = load_data()
    total_revenue = sum(o["total"] for o in data["orders"])
    return render_template("admin/dashboard.html",
        products=data["products"], orders=data["orders"],
        total_revenue=total_revenue)

@app.route("/admin/products")
@login_required
def admin_products():
    data = load_data()
    return render_template("admin/products.html", products=data["products"])

@app.route("/admin/products/add", methods=["GET", "POST"])
@login_required
def admin_add_product():
    if request.method == "POST":
        data = load_data()
        product = {
            "id": str(uuid.uuid4())[:8],
            "name": request.form["name"],
            "price": int(request.form["price"]),
            "category": request.form["category"],
            "description": request.form["description"],
            "image": request.form.get("image", "default.jpg"),
            "stock": int(request.form["stock"]),
            "featured": "featured" in request.form
        }
        data["products"].append(product)
        save_data(data)
        flash("Товар добавлен!", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", product=None)

@app.route("/admin/products/edit/<pid>", methods=["GET", "POST"])
@login_required
def admin_edit_product(pid):
    data = load_data()
    product = next((p for p in data["products"] if p["id"] == pid), None)
    if request.method == "POST":
        product.update({
            "name": request.form["name"],
            "price": int(request.form["price"]),
            "category": request.form["category"],
            "description": request.form["description"],
            "image": request.form.get("image", product["image"]),
            "stock": int(request.form["stock"]),
            "featured": "featured" in request.form
        })
        save_data(data)
        flash("Товар обновлён!", "success")
        return redirect(url_for("admin_products"))
    return render_template("admin/product_form.html", product=product)

@app.route("/admin/products/delete/<pid>")
@login_required
def admin_delete_product(pid):
    data = load_data()
    data["products"] = [p for p in data["products"] if p["id"] != pid]
    save_data(data)
    flash("Товар удалён!", "success")
    return redirect(url_for("admin_products"))

@app.route("/admin/orders")
@login_required
def admin_orders():
    data = load_data()
    return render_template("admin/orders.html", orders=data["orders"])

@app.route("/admin/orders/status/<oid>", methods=["POST"])
@login_required
def admin_order_status(oid):
    data = load_data()
    order = next((o for o in data["orders"] if o["id"] == oid), None)
    if order:
        order["status"] = request.form["status"]
        save_data(data)
    return redirect(url_for("admin_orders"))

if __name__ == "__main__":
    app.run(debug=True, port=5000)
