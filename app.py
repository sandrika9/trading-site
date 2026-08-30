from datetime import datetime, timedelta
from functools import wraps
import os
import secrets
import time

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_mail import Mail, Message
from openai import OpenAI
import psycopg2
import psycopg2.extras
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your_secret_key_here")

# DATABASE_URL - გამოყენებულია სწორი პაროლი სპეციალური სიმბოლოების გარეშე
DATABASE_URL = "postgresql://postgres.rnktcgfknokfdktfxjkb:Yourstats1231@aws-0-ap-northeast-2.pooler.supabase.com:6543/postgres"

# --- Flask-Mail კონფიგურაცია მეილების გასაგზავნად ---
app.config["MAIL_SERVER"] = "smtp.googlemail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "your_email@gmail.com")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "your_gmail_app_password")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get(
    "MAIL_USERNAME", "your_email@gmail.com"
)

mail = Mail(app)

openai_api_key = os.environ.get("OPENAI_API_KEY")
openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None


def get_db_connection():
    retries = 3
    delay = 2
    for i in range(retries):
        try:
            conn = psycopg2.connect(
                DATABASE_URL,
                sslmode="require",
                connection_factory=psycopg2.extras.DictConnection,
            )
            return conn
        except Exception as e:
            if i < retries - 1:
                time.sleep(delay)
                continue
            else:
                raise e


@app.context_processor
def inject_user_status():
    if "user_id" not in session:
        return {"user_is_paid": 0, "is_admin": False}

    username = session.get("username")
    is_admin = username == "sandrika"

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_paid FROM users WHERE id = %s", (session["user_id"],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        is_paid_val = user["is_paid"] if user else 0
        if is_admin or is_paid_val == 1:
            return {"user_is_paid": 1, "is_admin": is_admin}

        return {"user_is_paid": 0, "is_admin": is_admin}
    except Exception:
        return {"user_is_paid": 1 if is_admin else 0, "is_admin": is_admin}


# დეკორატორი მკაცრად პრემიუმ ფუნქციებისთვის
def paid_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("username") == "sandrika":
            return f(*args, **kwargs)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT is_paid FROM users WHERE id = %s", (session["user_id"],))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user or user["is_paid"] != 1:
            return redirect(url_for("pricing"))

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session or session.get("username") != "sandrika":
            flash("ამ გვერდზე წვდომა გაქვს მხოლოდ შენ!", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)

    return decorated_function


def get_or_create_user_settings(cursor, user_id):
    cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
    settings = cursor.fetchone()
    if not settings:
        cursor.execute(
            "INSERT INTO user_settings (user_id, initial_balance, target_balance, max_loss_limit) VALUES (%s, %s, %s, %s)",
            (user_id, 50000.0, 53000.0, 1000.0),
        )
        cursor.connection.commit()
        cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user_id,))
        settings = cursor.fetchone()
    return settings


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_paid"] = user["is_paid"]

            if username == "sandrika" or user["is_paid"] == 1:
                return redirect(url_for("index"))
            else:
                return redirect(url_for("pricing"))
        else:
            flash("არასწორი მომხმარებლის სახელი ან პაროლი", "error")

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        hashed_password = generate_password_hash(password)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM users WHERE username = %s OR email = %s",
                (username, email),
            )
            if cursor.fetchone():
                flash("მომხმარებელი ამ სახელით ან მეილით უკვე არსებობს.", "error")
                cursor.close()
                conn.close()
                return redirect(url_for("register"))

            cursor.execute(
                "INSERT INTO users (username, email, password, is_paid) VALUES (%s, %s, %s, 0)",
                (username, email, hashed_password),
            )
            conn.commit()
            cursor.close()
            conn.close()
            flash(
                "რეგისტრაცია წარმატებულია! გთხოვთ გაიაროთ ავტორიზაცია.", "success"
            )
            return redirect(url_for("login"))
        except Exception as e:
            print(e)
            flash("რეგისტრაციისას მოხდა შეცდომა.", "error")

    return render_template("register.html")


# --- პაროლის აღდგენის მოთხოვნა (Forgot Password) ---
@app.route("/forgot-password", methods=["GET", "POST"], endpoint="forgot_password")
def forgot_password_view():
    if request.method == "POST":
        email = request.form.get("email")

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, email FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            token = secrets.token_urlsafe(32)
            expiration = datetime.utcnow() + timedelta(hours=1)

            cursor.execute(
                "UPDATE users SET reset_token = %s, reset_token_expiration = %s WHERE id = %s",
                (token, expiration, user["id"]),
            )
            conn.commit()
            cursor.close()
            conn.close()

            reset_url = url_for("reset_password", token=token, _external=True)
            msg = Message("პაროლის აღდგენა - YourStats", recipients=[email])
            msg.body = f"""პაროლის აღსადგენად მიჰყევით ამ ბმულს:
{reset_url}

თუ ეს მოთხოვნა თქვენ არ გეკუთვნით, უბრალოდ უგულებელყავით ეს წერილი. ბმული ძალაშია 1 საათის განმავლობაში."""

            try:
                mail.send(msg)
                flash(
                    "პაროლის აღდგენის ინსტრუქცია გამოგზავნილია თქვენს მეილზე.",
                    "info",
                )
            except Exception as e:
                print(e)
                flash("მეილის გაგზავნა ვერ მოხერხდა. სცადეთ მოგვიანებით.", "error")
        else:
            cursor.close()
            conn.close()
            flash("მომხმარებელი ამ მეილით ვერ მოიძებნა.", "error")

        return redirect(url_for("forgot_password"))

    return render_template("reset_password.html")


# --- ახალი პაროლის მითითება ბმულით (Reset Password) ---
@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, reset_token_expiration FROM users WHERE reset_token = %s",
        (token,),
    )
    user = cursor.fetchone()

    if not user or user["reset_token_expiration"] < datetime.utcnow():
        cursor.close()
        conn.close()
        flash("აღდგენის ბმული არასწორია ან ვადა გაუვიდა.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password")
        hashed_password = generate_password_hash(new_password)

        cursor.execute(
            "UPDATE users SET password = %s, reset_token = NULL, reset_token_expiration = NULL WHERE id = %s",
            (hashed_password, user["id"]),
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash(
            "პაროლი წარმატებით შეიცვალა! ახლა შეგიძლიათ შეხვიდეთ სისტემაში.",
            "success",
        )
        return redirect(url_for("login"))

    cursor.close()
    conn.close()
    return render_template("reset_password.html", token=token)


@app.route("/pricing")
def pricing():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("pricing.html")


@app.route("/paddle-webhook", methods=["POST"])
def paddle_webhook():
    data = request.get_json()
    if not data:
        return jsonify(success=False), 400

    event_type = data.get("event_type")
    if event_type == "transaction.completed":
        data_obj = data.get("data", {})
        custom_data = data_obj.get("custom_data", {})
        user_id = custom_data.get("user_id")

        if user_id:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET is_paid = 1 WHERE id = %s", (user_id,))
            conn.commit()
            cursor.close()
            conn.close()

    return jsonify(success=True), 200


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INT PRIMARY KEY,
                initial_balance FLOAT DEFAULT 50000.0,
                target_balance FLOAT DEFAULT 53000.0,
                max_loss_limit FLOAT DEFAULT 1000.0
            )
        """)
        conn.commit()
    except Exception:
        conn.rollback()

    settings = get_or_create_user_settings(cursor, session["user_id"])
    initial_balance = float(settings["initial_balance"])
    target_balance = float(settings["target_balance"])
    max_loss_limit = float(settings["max_loss_limit"])

    cursor.execute(
        "SELECT * FROM trades WHERE user_id = %s ORDER BY id DESC",
        (session["user_id"],),
    )
    trades = cursor.fetchall()
    cursor.close()
    conn.close()

    current_balance = initial_balance
    total_pnl = 0.0
    wins = 0
    dataSource_trades = list(trades)
    total_trades = len(dataSource_trades)

    gross_profit = 0.0
    gross_loss = 0.0
    current_max_loss = max_loss_limit

    chart_data = []
    calendar_data = {}

    for t in reversed(dataSource_trades):
        pnl = t["pnl"]
        total_pnl += pnl
        current_balance += pnl

        if pnl > 0:
            wins += 1
            gross_profit += pnl
        elif pnl < 0:
            gross_loss += abs(pnl)
            current_max_loss -= abs(pnl)

        chart_data.append({"time": str(t["date"]), "value": current_balance})

    for t in dataSource_trades:
        trade_date = str(t["date"])
        pnl = t["pnl"]
        if trade_date not in calendar_data:
            calendar_data[trade_date] = 0.0
        calendar_data[trade_date] += pnl

    if current_max_loss < 0:
        current_max_loss = 0.0

    win_rate = round((wins / total_trades * 100), 1) if total_trades > 0 else 0

    if gross_loss > 0:
        profit_factor = round(gross_profit / gross_loss, 2)
    elif gross_profit > 0:
        profit_factor = round(gross_profit, 2)
    else:
        profit_factor = 0.0

    progress_pct = (
        round(
            (
                (current_balance - initial_balance)
                / (target_balance - initial_balance)
            )
            * 100,
            1,
        )
        if target_balance > initial_balance
        else 0
    )
    if progress_pct < 0:
        progress_pct = 0
    if progress_pct > 100:
        progress_pct = 100

    return render_template(
        "index.html",
        initial_balance=initial_balance,
        current_balance=current_balance,
        total_pnl=total_pnl,
        win_rate=win_rate,
        profit_factor=profit_factor,
        max_loss_limit=current_max_loss,
        target_balance=target_balance,
        progress_pct=progress_pct,
        chart_data=chart_data,
        calendar_data=calendar_data,
        daily_pnl=calendar_data,
        trades=trades,
    )


@app.route("/trades")
def trades_list():
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE user_id = %s ORDER BY id DESC",
        (session["user_id"],),
    )
    trades = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("trades.html", trades=trades)


@app.route("/trade/<int:id>")
def trade_detail(id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE id = %s AND user_id = %s",
        (id, session["user_id"]),
    )
    trade = cursor.fetchone()
    cursor.close()
    conn.close()

    if not trade:
        flash("ტრეიდი ვერ მოიძებნა.", "error")
        return redirect(url_for("trades_list"))

    return render_template("trade_detail.html", trade=trade)


@app.route("/add_trade", methods=["GET", "POST"])
def add_trade():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT is_paid FROM users WHERE id = %s", (session["user_id"],))
    user = cursor.fetchone()
    is_paid = user["is_paid"] if user else 0
    is_admin = session.get("username") == "sandrika"

    cursor.execute(
        "SELECT COUNT(*) FROM trades WHERE user_id = %s", (session["user_id"],)
    )
    trade_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    if not is_admin and is_paid != 1 and trade_count >= 3:
        flash(
            "უფასო ვერსიით შეგიძლია დაამატო მაქსიმუმ 3 ტრეიდი. შეიძინე პრემიუმი შეუზღუდავად სარგებლობისთვის.",
            "error",
        )
        return redirect(url_for("pricing"))

    if request.method == "POST":
        date = request.form.get("date")
        pair = request.form.get("pair")
        raw_direction = str(request.form.get("direction", "")).strip().lower()
        if "short" in raw_direction or "შორთ" in raw_direction or raw_direction == "s":
            direction = "SHORT"
        else:
            direction = "LONG"

        entry_price = float(request.form.get("entry_price", 0) or 0)
        exit_price = float(request.form.get("exit_price", 0) or 0)
        pnl = float(request.form.get("pnl", 0) or 0)
        emotion = request.form.get("emotion", "ნეიტრალური")
        comment = request.form.get("comment", "")
        screenshot_base64 = request.form.get("screenshot")

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                    INSERT INTO trades (user_id, date, pair, direction, entry_price, exit_price, pnl, emotion, comment, screenshot)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session["user_id"],
                    date,
                    pair,
                    direction,
                    entry_price,
                    exit_price,
                    pnl,
                    emotion,
                    comment,
                    screenshot_base64,
                ),
            )
            conn.commit()
            flash("ტრეიდი წარმატებით დაემატა!", "success")
        except Exception as e:
            conn.rollback()
            print("Error saving trade with comment/screenshot:", e)
            flash(f"შეცდომა ტრეიდის შენახვისას: {str(e)}", "error")
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("index"))

    return render_template("add_trade.html")


@app.route("/delete_trade/<int:id>", methods=["GET", "POST"])
def delete_trade(id):
    if "user_id" not in session:
        return redirect(url_for("login"))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE id = %s AND user_id = %s",
        (id, session["user_id"]),
    )
    trade = cursor.fetchone()
    if trade:
        cursor.execute("DELETE FROM trades WHERE id = %s", (id,))
        conn.commit()
        flash("ტრეიდი წაიშალა!", "success")
    cursor.close()
    conn.close()
    return redirect(url_for("trades_list"))


@app.route("/analytics")
@paid_required
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM trades WHERE user_id = %s ORDER BY id DESC",
        (session["user_id"],),
    )
    trades = cursor.fetchall()
    cursor.close()
    conn.close()

    long_wins = 0
    long_losses = 0
    long_pnl = 0.0

    short_wins = 0
    short_losses = 0
    short_pnl = 0.0

    emotion_stats = {}

    for t in trades:
        pnl = t["pnl"]
        raw_dir = str(t["direction"]).strip().lower() if t["direction"] else ""
        emotion = t.get("emotion") if t.get("emotion") else "ზოგადი"

        if emotion not in emotion_stats:
            emotion_stats[emotion] = {"count": 0, "pnl": 0.0}
        emotion_stats[emotion]["count"] += 1
        emotion_stats[emotion]["pnl"] += pnl

        is_short = (
            "short" in raw_dir or "შორთ" in raw_dir or raw_dir.startswith("s")
        )
        is_long = "long" in raw_dir or "ლონგ" in raw_dir or raw_dir.startswith("l")

        if is_short:
            if pnl >= 0:
                short_wins += 1
            else:
                short_losses += 1
            short_pnl += pnl
        elif is_long or not raw_dir:
            if pnl >= 0:
                long_wins += 1
            else:
                long_losses += 1
            long_pnl += pnl

    long_count = long_wins + long_losses
    short_count = short_wins + short_losses

    long_stats = {
        "count": long_count,
        "pnl": long_pnl,
        "win_rate": (
            round((long_wins / long_count * 100), 1) if long_count > 0 else 0
        ),
    }

    short_stats = {
        "count": short_count,
        "pnl": short_pnl,
        "win_rate": (
            round((short_wins / short_count * 100), 1) if short_count > 0 else 0
        ),
    }

    return render_template(
        "analytics.html",
        long_stats=long_stats,
        short_stats=short_stats,
        emotion_stats=emotion_stats,
    )


@app.route("/ai_insights", methods=["POST"])
@paid_required
def ai_insights():
    if not openai_client:
        return jsonify(
            {"advice": "OpenAI API გასაღები არ არის კონფიგურირებული სერვერზე."}
        )

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT pair, direction, pnl, emotion, comment, date FROM trades WHERE user_id = %s ORDER BY id DESC LIMIT 20",
        (session["user_id"],),
    )
    trades = cursor.fetchall()
    cursor.close()
    conn.close()

    if not trades:
        return jsonify(
            {"advice": "ჯერ არ გაქვს დამატებული ტრეიდები AI ანალიზისთვის."}
        )

    trades_summary = "\n".join(
        [
            f"Pair: {t['pair']}, Direction: {t['direction']}, PnL: {t['pnl']}, Emotion: {t.get('emotion', 'N/A')}, Comment: {t.get('comment', 'N/A')}, Date: {t['date']}"
            for t in trades
        ]
    )

    prompt = (
        "შენ ხარ პროფესიონალი ტრეიდინგ მენტორი და რისკ-მენეჯერი. "
        "გააანალიზე ამ ტრეიდერის ბოლო ტრეიდები და მომეცი მოკლე, კონკრეტული და რჩევებზე ორიენტირებული ანალიზი (ქართულ ენაზე):\n\n"
        f"{trades_summary}"
    )

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        advice = response.choices[0].message.content
        return jsonify({"advice": advice})
    except Exception as e:
        return jsonify(
            {
                "advice": f"ვერ მოხერხდა AI ანალიზის გენერაცია. (შეცდომა: {str(e)})"
            }
        )


@app.route("/update_settings", methods=["POST"])
def update_settings():
    if "user_id" not in session:
        return redirect(url_for("login"))
    initial_balance = float(request.form.get("initial_balance", 50000.0) or 50000.0)
    target_balance = float(request.form.get("target_balance", 53000.0) or 53000.0)
    max_loss_limit = float(request.form.get("max_loss_limit", 1000.0) or 1000.0)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INT PRIMARY KEY,
                initial_balance FLOAT DEFAULT 50000.0,
                target_balance FLOAT DEFAULT 53000.0,
                max_loss_limit FLOAT DEFAULT 1000.0
            )
        """)
        conn.commit()

        cursor.execute(
            """
            INSERT INTO user_settings (user_id, initial_balance, target_balance, max_loss_limit)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET initial_balance = %s, target_balance = %s, max_loss_limit = %s
            """,
            (
                session["user_id"],
                initial_balance,
                target_balance,
                max_loss_limit,
                initial_balance,
                target_balance,
                max_loss_limit,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        flash("შეცდომა პარამეტრების შენახვისას.", "error")
        print(e)
    finally:
        cursor.close()
        conn.close()

    flash("პარამეტრები წარმატებით განახლდა!", "success")
    return redirect(url_for("index"))


@app.route("/admin/users")
@admin_required
def admin_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, is_paid FROM users ORDER BY id ASC")
    all_users = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template("admin_users.html", users=all_users)


@app.route("/admin/toggle/<int:user_id>", methods=["POST"])
@admin_required
def toggle_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, is_paid FROM users WHERE id = %s", (user_id,))
    current = cursor.fetchone()

    if current:
        new_status = 0 if current["is_paid"] == 1 else 1
        cursor.execute(
            "UPDATE users SET is_paid = %s WHERE id = %s", (new_status, user_id)
        )
        conn.commit()

        if session.get("user_id") == user_id:
            session["is_paid"] = new_status

    cursor.close()
    conn.close()
    flash("სტატუსი განახლდა!", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    if session.get("user_id") == user_id:
        flash("საკუთარ თავს ვერ წაიშლი!", "error")
        return redirect(url_for("admin_users"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM user_settings WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash("მომხმარებელი და მისი მონაცემები წარმატებით წაიშალა!", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/edit_user/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        new_email = request.form.get("email")
        new_is_paid = int(request.form.get("is_paid", 0))

        cursor.execute(
            "UPDATE users SET email = %s, is_paid = %s WHERE id = %s",
            (new_email, new_is_paid, user_id),
        )
        conn.commit()
        cursor.close()
        conn.close()
        flash("მომხმარებლის მონაცემები განახლდა!", "success")
        return redirect(url_for("admin_users"))

    cursor.execute(
        "SELECT id, username, email, is_paid FROM users WHERE id = %s", (user_id,)
    )
    edit_target_user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not edit_target_user:
        flash("მომხმარებელი ვერ მოიძებნა.", "error")
        return redirect(url_for("admin_users"))

    render_target = render_template(
        "edit_user.html", edit_target_user=edit_target_user
    )
    return render_target


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
