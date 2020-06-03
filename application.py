import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd
import datetime
# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
    holdings = db.execute("SELECT * FROM holdings WHERE user_id = :user_id", user_id = session['user_id'])
    user = db.execute("SELECT * FROM users WHERE id = :user_id", user_id = session['user_id'])
    totalholding = 0
    user = user[0]
    for rows in holdings:
        print(rows)
        stockprice = lookup(rows['symbol'])
        total = {'total' : round(stockprice['price'] * rows['quantity'],2)}
        totalholding += total['total']
        print(totalholding)
        rows.update(stockprice)
        rows.update(total)

    print(holdings)
    print(user)
    user['cash'] = round(user['cash'], 2)
    networth = user['cash'] + totalholding
    print("net worth", networth)
    return render_template("index.html", holdings = holdings, user = user, totalholding = totalholding, networth = networth)

@app.route("/change_password", methods=["GET", "POST"])
@login_required
def change_password():
    if request.method == "GET":
        return render_template("changepw.html")
    else:
        if not request.form.get("newpassword"):
            return apology("enter new password")
        if request.form.get("newpassword") != request.form.get("confirmation"):
            return apology("password confirmation failed")
        oldhash = db.execute("SELECT hash FROM users WHERE id = :user_id", user_id = session["user_id"])
        oldhash = oldhash[0]['hash']
        newhash = generate_password_hash(request.form.get("newpassword"))
        if newhash == oldhash:
            return apology("select a new password")
        db.execute("UPDATE users SET hash = :newhash WHERE id = :user_id", newhash = newhash, user_id=session['user_id'])
        return render_template("pwchanged.html")

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")
    else:
        stock = lookup(request.form.get("symbol"))
        if not stock:
            return apology("Stock not found")
        if not request.form.get("quantity").isnumeric():
            return apology("Invalid quantity")
        balance = db.execute("SELECT cash FROM users WHERE id = :userid", userid = session["user_id"])
        print (balance)
        if stock['price'] * float(request.form.get("quantity")) > balance[0]['cash']:
            return apology("Insufficient funds")
        db.execute("INSERT INTO transactions (user_id, action, symbol, quantity, unit_price, total_price, 'date') VALUES (:user_id, :action, :symbol, :quantity, :unit_price, :total_price, :date)",
        user_id = session["user_id"], action ="BUY", symbol = stock["symbol"],quantity = request.form.get("quantity"),
        unit_price = stock["price"], total_price = stock['price'] * float(request.form.get("quantity")), date = datetime.datetime.now())

        checkifowns = db.execute("SELECT COUNT (user_id) FROM holdings WHERE symbol = :symbol AND user_id = :user_id", user_id = session['user_id'], symbol = stock['symbol'])
        print(checkifowns)
        if checkifowns[0]['COUNT (user_id)'] == 0:
            db.execute("INSERT INTO holdings (user_id, symbol, quantity) VALUES (:user_id, :symbol, :quantity)", user_id = session["user_id"], symbol = stock["symbol"], quantity = request.form.get("quantity"))
        else:
            db.execute("UPDATE holdings SET quantity = quantity + :quantity WHERE user_id = :user_id AND symbol = :symbol", quantity = request.form.get("quantity"), symbol = stock["symbol"], user_id = session['user_id'])



        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash = balance[0]['cash'] - stock['price'] * float(request.form.get("quantity")), user_id = session["user_id"])
    return redirect("/")


@app.route("/history")
@login_required
def history():
    transactions = db.execute ("SELECT * FROM transactions WHERE user_id = :user_id", user_id = session['user_id'])

    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")
    else:
        quote = lookup(request.form.get("symbol"))
        if not quote:
            return apology("Stock not found")
        return render_template("quoted.html",quote=quote)

    return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "GET":
        return render_template("register.html")
    else:
        if not request.form.get("username"):
            return apology("invalid username")

        usernameexists = db.execute("SELECT username FROM users WHERE username = :username",
                          username=request.form.get("username"))
        print (usernameexists)
    if request.form.get("username") == usernameexists[0]['username']:
        return apology("username already exists")
    if not request.form.get("password"):
        return apology("you must enter a password")

    if request.form.get("password") != request.form.get("confirmation"):
        return apology("password confirmation failed")

    db.execute("INSERT INTO users (username, hash) VALUES (:username, :hash)",
    username = request.form.get("username"), hash = generate_password_hash(request.form.get("password")))

    return redirect("/")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    if request.method == "GET":
        stocks = db.execute("SELECT symbol FROM holdings WHERE user_id = :user_id", user_id = session['user_id'])
        return render_template("sell.html",stocks=stocks)
    else:
        if not request.form.get("quantity").isnumeric():
            return apology("Invalid quantity")

        stock = lookup(request.form.get("symbol"))
        holdings = db.execute("SELECT * from holdings WHERE user_id = :user_id AND symbol = :symbol", user_id = session['user_id'], symbol = request.form.get("symbol"))
        if int(request.form.get("quantity")) > holdings[0]['quantity']:
            return apology("Excessive request")

        db.execute("INSERT INTO transactions (user_id, action, symbol, quantity, unit_price, total_price, 'date') VALUES (:user_id, :action, :symbol, :quantity, :unit_price, :total_price, :date)",
        user_id = session["user_id"], action ="SELL", symbol = stock["symbol"],quantity = request.form.get("quantity"),
        unit_price = stock["price"], total_price = stock['price'] * float(request.form.get("quantity")), date = datetime.datetime.now())

        newquantity = holdings[0]['quantity'] - int(request.form.get("quantity"))
        if newquantity == 0:
            db.execute("DELETE FROM holdings WHERE user_id=:user_id AND symbol = :symbol", user_id = session['user_id'], symbol = stock['symbol'])
        else:
            db.execute("UPDATE holdings set quantity = :quantity WHERE user_id = :user_id", quantity = newquantity, user_id = session['user_id'])
        money = db.execute("SELECT cash FROM users WHERE id = :user_id", user_id = session['user_id'])
        money = money[0]['cash']
        cash = money + stock['price'] * float(request.form.get("quantity"))
        db.execute("UPDATE users SET cash = :cash WHERE id = :user_id", cash = cash, user_id = session['user_id'])
        return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
