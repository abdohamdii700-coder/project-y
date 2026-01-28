import os
import re
import io
import base64
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
import matplotlib

# Fix for Matplotlib in Flask (Server Backend)
matplotlib.use('Agg')
import matplotlib.pyplot as plt

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'AFM27SuperSecret2026')

# ---------------------------------------------------------
# 1. DATABASE CONFIGURATION
# ---------------------------------------------------------
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ---------------------------------------------------------
# 2. LOAD DATA (EXCEL)
# ---------------------------------------------------------
try:
    sheet1_df = pd.read_excel("data.xlsx", sheet_name="Sheet1")
    sheet2_df = pd.read_excel("data.xlsx", sheet_name="Sheet2")
    # Clean IDs to strings
    sheet1_df['ID'] = sheet1_df['ID'].astype(str).str.strip()
    sheet2_df['ID'] = sheet2_df['ID'].astype(str).str.strip()
except Exception as e:
    print(f"Data Error: {e}")
    sheet1_df = pd.DataFrame()
    sheet2_df = pd.DataFrame()

try:
    residency_24_df = pd.read_excel("24.xlsx")
    residency_25_df = pd.read_excel("25.xlsx")
except:
    residency_24_df = pd.DataFrame()
    residency_25_df = pd.DataFrame()

# ---------------------------------------------------------
# 3. DATABASE MODELS
# ---------------------------------------------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    has_paid = db.Column(db.Boolean, default=False)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    status = db.Column(db.String(20), default='Pending')
    user = db.relationship('User', backref='payments')

class PreApproved(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(50), unique=True, nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------------------------------------
# 4. TEMPLATES (MERGED ORIGINAL DESIGN + AUTH)
# ---------------------------------------------------------

auth_style = """
<style>
    body { font-family: 'Arial', sans-serif; background-color: #f0f4f8; text-align: center; padding-top: 50px; direction: ltr; }
    .auth-box { background: white; width: 400px; margin: auto; padding: 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
    h2 { color: #333; margin-bottom: 20px; font-weight: 900; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    input { width: 90%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 25px; font-size: 16px; outline:none; text-align:center; }
    input:focus { border-color: #667eea; box-shadow: 0 0 5px rgba(102,126,234,0.3); }
    button { width: 95%; padding: 12px; background: linear-gradient(135deg, #667eea, #764ba2); color: white; border: none; border-radius: 25px; font-size: 18px; cursor: pointer; font-weight: bold; margin-top: 10px; }
    button:hover { opacity: 0.9; transform: translateY(-2px); }
    .flash { padding: 10px; border-radius: 10px; margin-bottom: 15px; color: white; font-weight: bold; }
    .error { background: #ff6b6b; }
    .success { background: #4caf50; }
    .telegram-btn { background: #229ED9; display: flex; align-items: center; justify-content: center; gap: 10px; text-decoration: none; padding: 12px; color: white; border-radius: 25px; font-weight: bold; margin-top: 15px; transition: 0.3s; }
    .telegram-btn:hover { background: #1b7fb0; transform: translateY(-2px); }
    a { color: #667eea; text-decoration: none; font-weight: bold; }
</style>
"""

login_html = f"""<!doctype html><html><head><title>Login - AFM 27</title>{auth_style}</head><body>
<div class="auth-box">
    <h2>🔐 AFM 27 Login</h2>
    {{% with messages = get_flashed_messages() %}}
      {{% if messages %}}<div class="flash error">{{{{ messages[0] }}}}</div>{{% endif %}}
    {{% endwith %}}
    <form method="POST">
        <input type="text" name="student_id" placeholder="Student ID (رقم الجلوس)" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>
    <p style="color:#777; margin-top:15px;">New User? <a href="/register">Create Account</a></p>
</div></body></html>"""

register_html = f"""<!doctype html><html><head><title>Register - AFM 27</title>{auth_style}</head><body>
<div class="auth-box">
    <h2>📝 Create Account</h2>
    {{% with messages = get_flashed_messages() %}}
      {{% if messages %}}<div class="flash error">{{{{ messages[0] }}}}</div>{{% endif %}}
    {{% endwith %}}
    <form method="POST">
        <input type="text" name="student_id" placeholder="Student ID (رقم الجلوس)" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Register</button>
    </form>
    <p style="font-size:13px; color:#d32f2f;">* Please use your REAL Student ID.</p>
    <p style="color:#777;">Already registered? <a href="/login">Login</a></p>
</div></body></html>"""

payment_html = f"""<!doctype html><html><head><title>Subscription</title>{auth_style}</head><body>
<div class="auth-box">
    <h2>💰 Subscription Required</h2>
    <p style="color:#555;">To access full results and analysis, please transfer <strong>100 EGP</strong>.</p>
    
    <div style="background: #ffebee; padding: 15px; border-radius: 15px; margin: 20px 0; border: 1px solid #ffcdd2;">
        <strong>Vodafone Cash:</strong><br>
        <span style="font-size: 24px; color: #c62828; font-weight:bold;">01002180473</span>
    </div>

    {{% with messages = get_flashed_messages() %}}
      {{% if messages %}}<div class="flash success">{{{{ messages[0] }}}}</div>{{% endif %}}
    {{% endwith %}}
    
    <form method="POST">
        <button type="submit">✅ I have transferred the amount</button>
    </form>
    
    <div style="margin: 20px 0; border-top: 1px solid #eee; padding-top: 10px;">
        <label style="font-size:14px; color:#555;">Send screenshot to Admin:</label>
        <a href="https://t.me/Abdo_Hamdi6" target="_blank" class="telegram-btn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="white"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.2-.08-.06-.19-.04-.27-.02-.11.02-1.93 1.23-5.46 3.62-.51.35-.98.52-1.4.51-.46-.01-1.35-.26-2.01-.48-.81-.27-1.44-.42-1.38-.88.03-.24.38-.49 1.03-.75 4.06-1.77 6.77-2.94 8.13-3.51 3.87-1.64 4.67-1.92 5.19-1.93.11 0 .37.03.54.17.14.12.18.28.2.45-.02.07-.02.13-.03.23z"/></svg>
            Contact on Telegram
        </a>
    </div>
    <br>
    <a href="/logout" style="color:#d32f2f">Logout</a>
</div></body></html>"""

admin_html = """
<!doctype html>
<html>
<head><title>Admin Panel</title><style>body{font-family:'Arial';padding:20px;background:#f0f4f8}.container{max-width:1000px;margin:auto;background:white;padding:20px;border-radius:10px;box-shadow:0 4px 15px rgba(0,0,0,0.1)}table{width:100%;border-collapse:collapse;margin-top:20px}th,td{padding:12px;border-bottom:1px solid #ddd;text-align:center}th{background:#333;color:white}.btn{padding:8px 15px;color:white;text-decoration:none;border-radius:5px}.approve{background:green}.logout{background:red;float:right}form{margin:20px 0;background:#e3f2fd;padding:15px;border-radius:8px;}</style></head>
<body>
    <div class="container">
        <h1 style="display:inline-block">👮 Admin Panel</h1>
        <a href="/logout" class="btn logout">Logout</a>
        <a href="/" class="btn" style="background:#2196f3; margin-left:10px;">View Site</a>
        
        <form method="POST" action="/admin/preapprove">
            <h3>⚡ Pre-Approve ID (Auto-Activate)</h3>
            <p style="margin:5px 0; font-size:14px; color:#555;">Enter ID here. When this student registers, they will be active immediately.</p>
            <input type="text" name="student_id" placeholder="Student ID" required style="padding:8px; width:200px;">
            <button type="submit" class="btn approve">Add to Whitelist</button>
        </form>

        <h3>📋 Pending Requests</h3>
        {% if requests %}
        <table>
            <tr><th>Student ID</th><th>Status</th><th>Action</th></tr>
            {% for req in requests %}
            <tr>
                <td>{{ req.user.student_id }}</td>
                <td>{{ req.status }}</td>
                <td><a href="/approve/{{ req.id }}" class="btn approve">✅ Approve</a></td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
            <p>No pending requests.</p>
        {% endif %}
    </div>
</body>
</html>
"""

# ---------------------------------------------------------
# 5. MAIN TEMPLATE (ORIGINAL STYLE & CHARTS RESTORED)
# ---------------------------------------------------------
html_template = """ 
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>AFM 27 RESULTS</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logoTB.png') }}">
    <style>
        body {
            font-family: 'Arial', sans-serif;
            background-color: #f0f4f8;
            text-align: center;
            position: relative;
        }
        body::before {
            content: "";
            background-image: url('https://i.ibb.co/zHRhsP6j');
            background-size: cover;
            background-position: center;
            opacity: 0.1;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            position: fixed;
            z-index: -1;
        }
        .container {
            margin: 60px auto;
            width: 70%;
            background-color: rgba(255, 255, 255, 0.9);
            padding: 20px 30px;
            border-radius: 10px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
        }
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 30px;
            direction: ltr;
        }
        .header-content { display: flex; align-items: center; gap: 20px; }
        .header img {
            height: 70px;
            width: auto;
            opacity: 0.85;
        }
        .header-text {
            text-align: left;
            direction: ltr;
        }
        .header-text h1 {
            font-size: 36px;
            margin: 0;
            font-weight: 900;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
            letter-spacing: 1px;
            font-family: 'Arial Black', sans-serif;
        }
        .header-text h1 a {
            text-decoration: none;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header-text p {
            font-size: 18px;
            margin: 5px 0 0 0;
            font-style: italic;
            font-weight: bold;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
        }
        .header-text p a {
            text-decoration: none;
            font-style: italic;
            font-weight: bold;
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .logout-btn {
            background: #f44336; color: white; padding: 10px 20px; border-radius: 20px; text-decoration: none; font-weight: bold; font-size: 14px; box-shadow: 0 4px 10px rgba(0,0,0,0.2); transition:0.3s;
        }
        .logout-btn:hover { background: #d32f2f; transform: translateY(-2px); }

        /* Navigation Buttons */
        .nav-buttons {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin: 30px 0;
            flex-wrap: wrap;
        }
        
        .nav-btn {
            padding: 15px 30px;
            font-size: 18px;
            font-weight: bold;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
        }
        
        .nav-btn.search { background: linear-gradient(45deg, #4285f4, #34a853); }
        .nav-btn.distance { background: linear-gradient(45deg, #ff6b6b, #4ecdc4); }
        .nav-btn.need { background: linear-gradient(45deg, #9c27b0, #e91e63); }
        .nav-btn.residency { background: linear-gradient(45deg, #f39c12, #e74c3c); }
        .nav-btn.admin { background: #333; }
        .nav-btn.active { background: linear-gradient(45deg, #333, #555); }
        .nav-btn:hover { transform: translateY(-3px); box-shadow: 0 6px 20px rgba(0,0,0,0.3); }
        
        table {
            border-collapse: collapse;
            margin: auto;
            width: 100%;
            font-size: 18px;
            direction: rtl;
            background-color: #fff;
        }
        th, td {
            border: 1px solid #ccc;
            padding: 10px;
            text-align: center;
        }
        th { width: 40%; }
        td { width: 60%; font-weight: bold; }
        .title {
            font-weight: bold;
            font-size: 20px;
            background-color: #b3e5fc;
            color: #000;
        }
        .footer { background-color: #a0d080; font-style: italic; }
        .first-year { background-color: #e0f7fa; }
        .second-year { background-color: #fff3e0; }
        .third-year { background-color: #ede7f6; }
        .fourth-year { background-color: #d0e0ff; }
        .totals { background-color: #d0f8ce; }
        .rank { background-color: #ffe0f0; }
        
        form { margin: 0 auto; display: flex; flex-direction: column; align-items: center; }
        label.title {
            font-size: 36px;
            font-weight: 800;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 25px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
            letter-spacing: 2px;
            text-transform: uppercase;
            font-family: 'Arial Black', sans-serif;
        }
        
        .search-container { position: relative; margin: 20px 0; }
        input[type="text"], input[type="number"] {
            font-size: 24px; padding: 15px 25px; width: 400px; border: 2px solid #ddd; border-radius: 25px; transition: all 0.3s ease; outline: none; box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        input[type="text"]:focus, input[type="number"]:focus { border-color: #4285f4; box-shadow: 0 0 15px rgba(66, 133, 244, 0.3); transform: scale(1.02); }
        input[type="submit"] {
            font-size: 20px; padding: 12px 30px; margin-top: 15px; border-radius: 25px; background: linear-gradient(45deg, #4285f4, #34a853); color: white; border: none; cursor: pointer; transition: all 0.3s ease; box-shadow: 0 4px 15px rgba(66, 133, 244, 0.3);
        }
        input[type="submit"]:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(66, 133, 244, 0.4); }
        
        p { font-size: 22px; color: red; }
        
        .distance-result {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 20px; margin: 30px 0; box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }
        .distance-result h2 { font-size: 32px; margin-bottom: 20px; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        
        .progress-arrow-container { display: flex; align-items: center; justify-content: center; margin: 30px 0; position: relative; direction: ltr; }
        .progress-circle { width: 140px; height: 140px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; color: white; font-weight: bold; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); position: relative; z-index: 2; }
        .current-circle { background: linear-gradient(135deg, #ff6b6b, #ee5a52); box-shadow: 0 8px 20px rgba(255, 107, 107, 0.4); }
        .target-circle { background: linear-gradient(135deg, #4ecdc4, #44a08d); box-shadow: 0 8px 20px rgba(78, 205, 196, 0.4); }
        .circle-label { font-size: 16px; margin-bottom: 5px; opacity: 0.9; }
        .circle-value { font-size: 26px; font-weight: 900; }
        .progress-arrow { flex: 0 0 200px; height: 12px; background: linear-gradient(90deg, #ff6b6b, #4ecdc4); margin: 0 25px; border-radius: 6px; position: relative; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .progress-arrow::after { content: ''; position: absolute; right: -18px; top: 50%; transform: translateY(-50%); width: 0; height: 0; border-left: 22px solid #4ecdc4; border-top: 20px solid transparent; border-bottom: 20px solid transparent; filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.3)); }
        .progress-difference { position: absolute; top: -50px; left: 50%; transform: translateX(-50%); background: rgba(255,255,255,0.95); color: #333; padding: 12px 20px; border-radius: 25px; font-size: 18px; font-weight: bold; box-shadow: 0 4px 15px rgba(0,0,0,0.2); z-index: 3; white-space: nowrap; min-width: 120px; text-align: center; }
        .progress-difference.positive { background: linear-gradient(135deg, #4CAF50, #45a049); color: white; }
        .progress-difference.negative { background: linear-gradient(135deg, #f44336, #e53935); color: white; }
        .progress-difference.neutral { background: linear-gradient(135deg, #2196F3, #1976D2); color: white; }
        
        .motivational-message {
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4); color: white; padding: 25px; border-radius: 15px; margin: 20px 0; font-size: 28px; font-weight: bold; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); line-height: 1.4;
        }
        .motivational-message .highlight-number { font-size: 36px; text-decoration: underline; font-weight: 900; }
        
        .chart-title {
            font-size: 26px; font-weight: bold; color: #2c3e50; margin: 30px 0 20px 0; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        }
        
        .percentile-box {
            background: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1, #96ceb4); background-size: 400% 400%; animation: gradientShift 3s ease infinite; color: white; font-size: 22px; font-weight: bold; padding: 20px; margin: 20px auto; border-radius: 20px; box-shadow: 0 8px 25px rgba(0,0,0,0.3); text-shadow: 2px 2px 4px rgba(0,0,0,0.5); border: 3px solid white; max-width: 500px; position: relative; overflow: hidden;
        }
        .percentile-box::before { content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%; background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent); transform: rotate(45deg); animation: shine 2s infinite; }
        @keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        @keyframes shine { 0% { transform: translateX(-100%) translateY(-100%) rotate(45deg); } 100% { transform: translateX(100%) translateY(100%) rotate(45deg); } }
        
        .free-palestine {
            margin-top: 40px; padding: 25px; font-size: 24px; font-weight: bold; color: white; background: linear-gradient(90deg, black 25%, white 25% 50%, green 50% 75%, red 75% 100%); border-radius: 12px; text-shadow: 1px 1px 2px #000;
        }
        .dual-input { display: flex; gap: 20px; align-items: center; flex-wrap: wrap; justify-content: center; direction: ltr; }
        .dual-input input { width: 180px; }
        .dual-input label { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 5px; display: block; }
    </style>
    <script>
      window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };
    </script>
    <script defer src="/_vercel/insights/script.js"></script>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-content">
                <img src="https://i.postimg.cc/0rHzBdbx/8.jpg" alt="Logo">
                <div class="header-text">
                    <h1><a href="/">AFM 27 Results & Analysis</a></h1>
                    <p><a href="https://t.me/Abdo_Hamdi6" target="_blank">By : Abdo Hamdy Aly</a></p>
                    <p style="font-size:14px; margin-top:5px; color:#555;">ID: {{ current_user.student_id }}</p>
                </div>
            </div>
            <a href="/logout" class="logout-btn">🚪 Logout</a>
        </div>

        <div class="nav-buttons">
            <a href="/?mode=search" class="nav-btn search {{ 'active' if mode == 'search' or not mode else '' }}">
                🔍 My Result
            </a>
            <a href="/?mode=distance" class="nav-btn distance {{ 'active' if mode == 'distance' else '' }}">
                📏 How Far I am
            </a>
            <a href="/?mode=need" class="nav-btn need {{ 'active' if mode == 'need' else '' }}">
                🎯 How Much I Need
            </a>
            <a href="/residency?year=2024" class="nav-btn residency">
                🏥 Residency Matching
            </a>
            {% if current_user.is_admin %}
                <a href="/admin" class="nav-btn admin">👮 Admin Panel</a>
            {% endif %}
        </div>

        {% if mode == 'need' %}
        <form method="POST" action="/?mode=need">
            <label class="title">HOW MUCH I NEED</label><br>
            <div class="search-container">
                <div class="dual-input">
                    <div>
                        <label>Target Total %</label>
                        <input type="number" name="target_percentage" step="0.01" min="0" max="100" placeholder="Target %" required>
                    </div>
                </div>
                <br>
                <input type="submit" value="🧮 Calculate Required">
            </div>
        </form>

        {% if need_result %}
        <div class="distance-result">
            <h2>🎯 Required Analysis (Remaining 1.5 Years)</h2>
            <h3 style="font-size: 30px; margin: 15px 0; color: #ffeb3b; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);">{{ need_result['student_name'] }}</h3>
            
            <div class="progress-arrow-container">
                <div class="progress-circle current-circle">
                    <div class="circle-label">Current (4 Yrs)</div>
                    <div class="circle-value">{{ need_result['current_percentage'] }}%</div>
                </div>
                
                <div class="progress-arrow">
                    <div class="progress-difference {% if need_result['required_coming_percentage'] > 0 and need_result['required_coming_percentage'] <= 100 %}positive{% elif need_result['required_coming_percentage'] > 100 %}negative{% else %}neutral{% endif %}">
                        {% if need_result['required_coming_percentage'] > 100 %}
                            Impossible (>100%)
                        {% elif need_result['required_coming_percentage'] < 0 %}
                            Target Achieved!
                        {% else %}
                            Need {{ need_result['required_coming_percentage'] }}%
                        {% endif %}
                    </div>
                </div>
                
                <div class="progress-circle target-circle">
                    <div class="circle-label">Target Total</div>
                    <div class="circle-value">{{ need_result['target_percentage'] }}%</div>
                </div>
            </div>
            
            <div class="motivational-message">
                To reach <span class="highlight-number">{{ need_result['target_percentage'] }}%</span> Total,<br>
                You need to score <span class="highlight-number">{{ need_result['required_coming_score'] }}</span> marks 
                out of 1695 in the coming 1.5 years.<br>
                (Approx <span class="highlight-number">{{ need_result['required_coming_percentage'] }}%</span> of the remaining total)
            </div>
        </div>
        {% endif %}

        {% elif mode == 'distance' %}
        <form method="POST" action="/?mode=distance">
            <label class="title">HOW FAR I AM</label><br>
            <div class="search-container">
                <div class="dual-input">
                    <div>
                        <label>Target Rank</label>
                        <input type="number" name="target_rank" min="1" placeholder="Target rank" required>
                    </div>
                </div>
                <br>
                <input type="submit" value="🎯 Calculate Distance">
            </div>
        </form>

        {% if distance_result %}
        <div class="distance-result">
            <h2>📊 Distance Analysis</h2>
            <h3 style="font-size: 30px; margin: 15px 0; color: #ffeb3b; text-shadow: 2px 2px 4px rgba(0,0,0,0.5);">{{ distance_result['student_name'] }}</h3>
            
            <div class="progress-arrow-container">
                <div class="progress-circle current-circle">
                    <div class="circle-label">Current</div>
                    <div class="circle-value">#{{ distance_result['current_rank'] }}</div>
                </div>
                
                <div class="progress-arrow">
                    <div class="progress-difference {% if distance_result['points_needed'] > 0 %}positive{% elif distance_result['points_needed'] == 0 %}neutral{% else %}negative{% endif %}">
                        {% if distance_result['points_needed'] > 0 %}
                            {{ distance_result['points_needed'] }} Marks Behind
                        {% elif distance_result['points_needed'] == 0 %}
                            At Target!
                        {% else %}
                            {{ distance_result['points_needed']|abs }} Marks Ahead
                        {% endif %}
                    </div>
                </div>
                
                <div class="progress-circle target-circle">
                    <div class="circle-label">Target</div>
                    <div class="circle-value">#{{ distance_result['target_rank'] }}</div>
                </div>
            </div>
            
            {% if distance_result['points_needed'] > 0 %}
                <div class="motivational-message">
                    📏 The difference between your current rank (#{{ distance_result['current_rank'] }}) and rank #{{ distance_result['target_rank'] }} is <span class="highlight-number">{{ distance_result['points_needed'] }}</span> marks.
                    <br><br>Keep pushing forward! 💪
                </div>
            {% elif distance_result['points_needed'] == 0 %}
                <div class="motivational-message" style="background: linear-gradient(45deg, #4CAF50, #45a049);">
                    🎉 Congratulations! You're exactly at rank #{{ distance_result['target_rank'] }}! 
                    <br><br>Perfect achievement! 🏆
                </div>
            {% else %}
                <div class="motivational-message" style="background: linear-gradient(45deg, #4CAF50, #45a049);">
                    🌟 You're ahead of your target! The difference between rank #{{ distance_result['target_rank'] }} and your current rank (#{{ distance_result['current_rank'] }}) is <span class="highlight-number">{{ distance_result['points_needed']|abs }}</span> marks.
                    <br><br>You're doing great! Keep it up! 🔥
                </div>
            {% endif %}
        </div>
        {% endif %}

        {% else %}
        {% if result %}
        <table>
            <tr><td colspan="2" class="title">👨‍🎓 اسم الطالب : {{ result['NAME'] }}</td></tr>
            <tr><th class="title">🔢 MARK</th><th class="title">📚 SUBJECT</th></tr>
            {% for key, value in result.items() %}
                {% if key != 'ID' and key != 'NAME' %}
                    {% set key_upper = key.upper().strip() %}
                    {% if key_upper in ['FIRST YEAR', 'LONG FIRST YEAR', 'RESEARCH STEP I', 'COMMUNICATION STEP I', 'PROFESSIONALISM STEP I'] %}
                        {% set css_class = 'first-year' %}
                    {% elif key_upper in ['SECOND YEAR', 'LONG SECOND YEAR', 'RESEARCH STEP II', 'COMMUNICATION STEP II', 'PROFESSIONALISM STEP II'] %}
                        {% set css_class = 'second-year' %}
                    {% elif key_upper in ['THIRD YEAR', 'LONG THIRD YEAR', 'RESEARCH STEP III', 'COMMUNICATION STEP III', 'PROFESSIONALISM STEP III'] %}
                        {% set css_class = 'third-year' %}
                    {% elif key_upper in ['FOURTH YEAR', 'LONG FOURTH YEAR', 'RESEARCH STEP IIII', 'COMMUNICATION STEP IIII', 'PROFESSIONALISM STEP IIII'] %}
                        {% set css_class = 'fourth-year' %}
                    {% elif key_upper in ['TOTAL', 'TOTAL RANK', '%', 'PERCENTAGE'] %}
                        {% set css_class = 'totals' %}
                    {% elif 'RANK' in key_upper %}
                        {% set css_class = 'rank' %}
                    {% else %}
                        {% set css_class = '' %}
                    {% endif %}
                    <tr class="{{ css_class }}"><td>{{ value }}</td><td>{{ key }}</td></tr>
                {% endif %}
            {% endfor %}
            <tr class="footer"><td colspan="2">💻 Designed and Coded By : Abdo Hamdy Aly</td></tr>
            <tr>
                <td colspan="2" style="text-align: center; font-size: 18px; padding: 15px;">
                    <a href="https://t.me/Abdo_Hamdi6" target="_blank" style="text-decoration: none; color: black;">
                        <img src="https://upload.wikimedia.org/wikipedia/commons/8/82/Telegram_logo.svg" alt="Telegram" style="width: 24px; vertical-align: middle; margin-left: 8px;">
                        📱 @Abdo_Hamdi6
                    </a>
                </td>
            </tr>
        </table>

        {% if plot_url %}
            <div class="chart-title">📈 Student Score Distribution</div>
            <img src="data:image/png;base64,{{ plot_url }}">
            {% if percentile %}
                <div class="percentile-box">
                    🎯 YOU ARE IN THE {{ percentile }}th PERCENTILE! 🏆
                </div>
            {% endif %}
        {% endif %}

        {% if rank_progress_url %}
            <div class="chart-title">📊 Cumulative Rank Progress</div>
            <img src="data:image/png;base64,{{ rank_progress_url }}">
        {% endif %}

        {% else %}
            <p>❌ Student data not found. Please contact admin.</p>
        {% endif %}
        {% endif %}

           
</body>
</html>
"""

residency_template = """
<!doctype html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>Residency Matching Results</title>
    <link rel="icon" type="image/png" href="{{ url_for('static', filename='logoTB.png') }}">
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f0f4f8; text-align: center; position: relative; }
        body::before { content: ""; background-image: url('https://i.ibb.co/zHRhsP6j'); background-size: cover; background-position: center; opacity: 0.1; top: 0; left: 0; bottom: 0; right: 0; position: fixed; z-index: -1; }
        .container { margin: 60px auto; width: 90%; max-width: 1400px; background-color: rgba(255, 255, 255, 0.9); padding: 20px 30px; border-radius: 10px; box-shadow: 0 0 15px rgba(0,0,0,0.1); }
        .nav-buttons { display: flex; justify-content: center; gap: 20px; margin: 30px 0; flex-wrap: wrap; }
        .nav-btn { padding: 15px 30px; font-size: 18px; font-weight: bold; border: none; border-radius: 25px; cursor: pointer; text-decoration: none; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .nav-btn.home { background: linear-gradient(45deg, #667eea, #764ba2); }
        .nav-btn.year-2024 { background: linear-gradient(45deg, #ff6b6b, #ee5a52); }
        .nav-btn.year-2025 { background: linear-gradient(45deg, #4ecdc4, #44a08d); }
        .nav-btn.active { background: linear-gradient(45deg, #333, #555); }
        .stats-container { display: flex; justify-content: center; gap: 30px; margin: 30px 0; flex-wrap: wrap; }
        .stat-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px 40px; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
        .stat-number { font-size: 36px; font-weight: bold; margin: 10px 0; }
        .stat-label { font-size: 16px; opacity: 0.9; }
        .table-container { overflow-x: auto; margin: 30px 0; }
        table { border-collapse: collapse; margin: 0 auto; width: 100%; font-size: 16px; direction: rtl; background-color: #fff; box-shadow: 0 4px 15px rgba(0,0,0,0.1); border-radius: 10px; overflow: hidden; }
        th { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 10px; }
        td { padding: 12px 10px; border: 1px solid #ddd; }
        .boast-yes { background-color: #c8e6c9 !important; font-weight: bold; }
        .boast-no { background-color: #ffe0b2 !important; }
        .search-box { margin: 20px 0; padding: 15px; background: rgba(255,255,255,0.5); border-radius: 10px; }
        .search-box input { font-size: 18px; padding: 10px 20px; width: 300px; border: 2px solid #ddd; border-radius: 25px; outline: none; }
    </style>
    <script>
        function filterTable() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toUpperCase();
            const table = document.getElementById('residencyTable');
            const tr = table.getElementsByTagName('tr');
            for (let i = 1; i < tr.length; i++) {
                let found = false;
                const td = tr[i].getElementsByTagName('td');
                for (let j = 0; j < td.length; j++) {
                    if (td[j] && (td[j].textContent || td[j].innerText).toUpperCase().indexOf(filter) > -1) {
                        found = true; break;
                    }
                }
                tr[i].style.display = found ? '' : 'none';
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>🏥 Residency Matching {{ year }}</h1>
        <div class="nav-buttons">
            <a href="/" class="nav-btn home">🏠 Home</a>
            <a href="/residency?year=2024" class="nav-btn year-2024 {{ 'active' if year == '2024' else '' }}">2024</a>
            <a href="/residency?year=2025" class="nav-btn year-2025 {{ 'active' if year == '2025' else '' }}">2025</a>
        </div>
        
        {% if df_empty %}
            <p style="color:red; font-size:22px;">⚠️ No data available</p>
        {% else %}
            <div class="stats-container">
                <div class="stat-box"><div class="stat-label">Total</div><div class="stat-number">{{ results|length }}</div></div>
                <div class="stat-box" style="background:#4ecdc4"><div class="stat-label">With Post</div><div class="stat-number">{{ boast_count }}</div></div>
                <div class="stat-box" style="background:#ff6b6b"><div class="stat-label">Without Post</div><div class="stat-number">{{ no_boast_count }}</div></div>
            </div>
            <div class="search-box"><input type="text" id="searchInput" onkeyup="filterTable()" placeholder="🔍 Search..."></div>
            <div class="table-container">
                <table id="residencyTable">
                    <thead><tr><th>RANK</th><th>RESIDENCY</th><th>STATUS</th></tr></thead>
                    <tbody>
                        {% for row in results %}
                        <tr class="{% if row.get('STATUS') == 'بوست' %}boast-yes{% elif row.get('STATUS') == 'بدون بوست' %}boast-no{% endif %}">
                            <td class="rank-col">{{ row.get('RANK') }}</td><td>{{ row.get('RESIDENCY') }}</td><td>{{ row.get('STATUS') }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% endif %}
    </div>
</body>
</html>
"""

# ---------------------------------------------------------
# 6. ROUTES
# ---------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main'))
    
    if request.method == 'POST':
        student_id = request.form.get('student_id').strip()
        password = request.form.get('password')
        
        if sheet1_df.empty:
            flash('Error: Database not loaded.')
            return redirect(url_for('register'))
            
        # 1. Check Admin
        if student_id.upper() == 'ADMIN':
            if not User.query.filter_by(student_id='ADMIN').first():
                new_admin = User(student_id='ADMIN', password=generate_password_hash(password), is_admin=True, has_paid=True)
                db.session.add(new_admin)
                db.session.commit()
            flash('Admin account recognized.', 'success')
            return redirect(url_for('login'))

        # 2. Check Excel
        if sheet1_df[sheet1_df['ID'] == student_id].empty:
            flash('Error: ID not found in records.', 'error')
            return redirect(url_for('register'))
            
        # 3. Check Duplicate
        if User.query.filter_by(student_id=student_id).first():
            flash('Account already exists.', 'error')
            return redirect(url_for('register'))

        # 4. Check Pre-Approved
        is_preapproved = False
        if PreApproved.query.filter_by(student_id=student_id).first():
            is_preapproved = True

        new_user = User(student_id=student_id, password=generate_password_hash(password), has_paid=is_preapproved)
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registered successfully. Please login.', 'success')
        return redirect(url_for('login'))
        
    return render_template_string(register_html)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main'))
    if request.method == 'POST':
        student_id = request.form.get('student_id').strip()
        if student_id.upper() == 'ADMIN': student_id = 'ADMIN'
        
        password = request.form.get('password')
        user = User.query.filter_by(student_id=student_id).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('main'))
        flash('Invalid ID or Password.', 'error')
    return render_template_string(login_html)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/payment', methods=['GET', 'POST'])
@login_required
def payment():
    if current_user.has_paid or current_user.is_admin:
        return redirect(url_for('main'))
    
    if request.method == 'POST':
        if Payment.query.filter_by(user_id=current_user.id, status='Pending').first():
            flash('Request already sent.', 'error')
        else:
            new_req = Payment(user_id=current_user.id)
            db.session.add(new_req)
            db.session.commit()
            flash('Request Sent! Please contact admin on Telegram.', 'success')
            
    return render_template_string(payment_html)

@app.route('/admin', methods=['GET', 'POST'])
@login_required
def admin_panel():
    if not current_user.is_admin: return "Access Denied", 403
    
    requests = Payment.query.filter_by(status='Pending').all()
    return render_template_string(admin_html, requests=requests)

# Pre-Approve Logic
@app.route('/admin/preapprove', methods=['POST'])
@login_required
def preapprove_id():
    if not current_user.is_admin: return redirect(url_for('main'))
    sid = request.form.get('student_id').strip()
    
    # 1. Check if user already registered -> Activate
    existing_user = User.query.filter_by(student_id=sid).first()
    if existing_user:
        existing_user.has_paid = True
        pay_req = Payment.query.filter_by(user_id=existing_user.id, status='Pending').first()
        if pay_req: pay_req.status = 'Approved'
        db.session.commit()
        flash(f'User {sid} activated.', 'success')
    else:
        # 2. Add to Whitelist
        if not PreApproved.query.filter_by(student_id=sid).first():
            db.session.add(PreApproved(student_id=sid))
            db.session.commit()
            flash(f'ID {sid} added to whitelist.', 'success')
        else:
            flash(f'ID {sid} is already whitelisted.', 'error')
            
    return redirect(url_for('admin_panel'))

@app.route('/approve/<int:req_id>')
@login_required
def approve_payment(req_id):
    if not current_user.is_admin: return redirect(url_for('main'))
    req = Payment.query.get(req_id)
    if req:
        req.status = 'Approved'
        user = User.query.get(req.user_id)
        if user: user.has_paid = True
        db.session.commit()
    return redirect(url_for('admin_panel'))

# ---------------------------------------------------------
# 7. MAIN LOGIC (UPDATED MATH + ORIGINAL CHARTS)
# ---------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
@login_required
def main():
    if not current_user.has_paid and not current_user.is_admin:
        return redirect(url_for('payment'))

    student_id = current_user.student_id
    mode = request.args.get('mode', 'search')
    
    result = None
    plot_url = None
    rank_progress_url = None
    percentile = None
    need_result = None
    distance_result = None

    # Constants
    CURRENT_TOTAL_MAX = 3180 
    FINAL_TOTAL_MAX = 4875
    REMAINING_MAX = 1695

    if mode == 'search':
        if not sheet1_df.empty:
            match = sheet1_df[sheet1_df['ID'] == student_id]
            if not match.empty:
                raw = match.iloc[0].to_dict()
                formatted = {}
                for k, v in raw.items():
                    if isinstance(v, float):
                        if '%' in k or k.upper() in ['%', 'PERCENTAGE']:
                            formatted[k] = f"{round(v*100, 2)}%" if v <= 1 else f"{round(v, 2)}%"
                        elif v.is_integer():
                            formatted[k] = int(v)
                        else:
                            formatted[k] = round(v, 2)
                    else:
                        formatted[k] = v
                result = formatted
                
                # RESTORED PLOT 1 (Exact features)
                try:
                    total_scores = sheet1_df['TOTAL'].dropna()
                    student_score = raw.get('TOTAL')
                    if pd.notna(student_score):
                        percentile = round((total_scores < student_score).mean() * 100)
                        avg_score = total_scores.mean()
                        avg_pct = (avg_score / CURRENT_TOTAL_MAX) * 100
                        
                        plt.figure(figsize=(8, 5))
                        plt.hist(total_scores, bins=20, color='#66b3ff', edgecolor='black')
                        plt.axvline(student_score, color='orange', linestyle='solid', linewidth=2, label=f'Student Score: {student_score}')
                        plt.axvline(avg_score, color='black', linestyle='dashed', linewidth=2, label=f'Class Average ({round(avg_pct, 2)}%)')
                        
                        ymax = plt.gca().get_ylim()[1]
                        y_line = ymax * 0.7
                        plt.hlines(y_line, min(avg_score, student_score), max(avg_score, student_score), colors='red', linestyles='dashed', linewidth=2)
                        
                        mid_x = (student_score + avg_score) / 2
                        diff_pct = round(abs(student_score - avg_score) / CURRENT_TOTAL_MAX * 100, 1)
                        plt.text(mid_x, y_line + ymax * 0.03, f'{diff_pct}%', fontsize=10, fontweight='bold', ha='center', color='red')
                        
                        plt.plot([], [], 'r--', label='% above/below average') # Legacy label restoration
                        plt.xlabel('Scores')
                        plt.ylabel('Number of Students')
                        plt.title('Score Distribution with Student Highlighted')
                        plt.legend()
                        
                        buf = io.BytesIO()
                        plt.savefig(buf, format='png')
                        buf.seek(0)
                        plot_url = base64.b64encode(buf.getvalue()).decode('utf8')
                        buf.close()
                        plt.close()
                except Exception as e:
                    print(f"Plot 1 Error: {e}")

                # RESTORED PLOT 2 (Exact features + Arrows)
                try:
                    if not sheet2_df.empty:
                        rank_match = sheet2_df[sheet2_df['ID'] == student_id]
                        if not rank_match.empty:
                            rank_data = rank_match.iloc[0].to_dict()
                            rank_cols = {
                                "FIRST YEAR RANK": ("FIRST YEAR", "#e0f7fa"),
                                "SECOND YEAR RANK C": ("SECOND YEAR", "#fff3e0"),
                                "THIRD YEAR RANK C": ("THIRD YEAR", "#ede7f6"),
                                "FOURTH YEAR RANK C": ("FOURTH YEAR", "#d0e0ff"),
                            }
                            labels, values, colors = [], [], []
                            for col, (lbl, clr) in rank_cols.items():
                                val = rank_data.get(col)
                                if pd.notna(val):
                                    labels.append(lbl)
                                    values.append(val)
                                    colors.append(clr)
                            
                            if labels:
                                plt.figure(figsize=(8, 5))
                                plt.plot(labels, values, marker='o', linestyle='-', color='black', linewidth=2)
                                for i in range(len(labels)):
                                    plt.plot(labels[i], values[i], '3', markersize=10, color=colors[i])
                                    plt.text(labels[i], values[i]+0.5, f'{int(values[i])}', ha='center', va='top', fontsize=14, fontweight='bold', color='black', bbox=dict(boxstyle='round,pad=0.4', facecolor='white', edgecolor='black'))
                                    
                                    # Arrow Logic from original code
                                    if i > 0:
                                        change = values[i-1] - values[i]
                                        c_color = 'green' if change > 0 else 'red'
                                        sign = '+' if change > 0 else ''
                                        arrow = '⬆' if change > 0 else '⬇'
                                        mid_x = (i - 0.5)
                                        mid_y = (values[i-1] + values[i]) / 2
                                        plt.text(mid_x, mid_y + 2.5, f'{arrow} {sign}{abs(int(change))}', fontsize=11, fontweight='bold', color=c_color, ha='center', va='top', bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor=c_color))

                                plt.ylabel('Cumulative Rank')
                                plt.title('Cumulative Progress Based on Class Rank')
                                plt.gca().invert_yaxis()
                                plt.grid(True)
                                
                                buf2 = io.BytesIO()
                                plt.savefig(buf2, format='png')
                                buf2.seek(0)
                                rank_progress_url = base64.b64encode(buf2.getvalue()).decode('utf8')
                                buf2.close()
                                plt.close()
                except Exception as e:
                    print(f"Plot 2 Error: {e}")

    elif mode == 'need' and request.method == 'POST':
        try:
            target_pct = float(request.form.get('target_percentage'))
            match = sheet1_df[sheet1_df['ID'] == student_id]
            if not match.empty:
                data = match.iloc[0]
                curr_total = data.get('TOTAL', 0)
                curr_pct = (curr_total / CURRENT_TOTAL_MAX) * 100
                req_total_marks = (target_pct / 100) * FINAL_TOTAL_MAX
                req_coming_marks = req_total_marks - curr_total
                req_coming_pct = (req_coming_marks / REMAINING_MAX) * 100
                
                need_result = {
                    'student_name': data.get('NAME'),
                    'current_percentage': round(curr_pct, 2),
                    'target_percentage': target_pct,
                    'required_coming_score': round(req_coming_marks, 2),
                    'required_coming_percentage': round(req_coming_pct, 2)
                }
        except: pass

    elif mode == 'distance' and request.method == 'POST':
        try:
            target_rank = int(request.form.get('target_rank'))
            match = sheet1_df[sheet1_df['ID'] == student_id]
            if not match.empty:
                curr_score = match.iloc[0]['TOTAL']
                curr_rank = (sheet1_df['TOTAL'] > curr_score).sum() + 1
                sorted_df = sheet1_df.sort_values('TOTAL', ascending=False).reset_index(drop=True)
                if target_rank <= len(sorted_df):
                    target_score = sorted_df.iloc[target_rank - 1]['TOTAL']
                    diff = target_score - curr_score
                    distance_result = {
                        'student_name': match.iloc[0]['NAME'],
                        'current_rank': curr_rank,
                        'target_rank': target_rank,
                        'points_needed': round(diff, 2)
                    }
        except: pass

    return render_template_string(html_template, 
                                  mode=mode, result=result, plot_url=plot_url, 
                                  rank_progress_url=rank_progress_url, percentile=percentile,
                                  need_result=need_result, distance_result=distance_result)

@app.route('/residency')
@login_required
def residency_page():
    if not current_user.has_paid and not current_user.is_admin:
        return redirect(url_for('payment'))
    year = request.args.get('year', '2024')
    df = residency_25_df if year == '2025' else residency_24_df
    results = []
    boast = 0; no_boast = 0
    if not df.empty:
        results = df.to_dict('records')
        for r in results:
            if str(r.get('STATUS')).strip() == 'بوست': boast+=1
            elif str(r.get('STATUS')).strip() == 'بدون بوست': no_boast+=1
    return render_template_string(residency_template, year=year, results=results, df_empty=df.empty, boast_count=boast, no_boast_count=no_boast)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)