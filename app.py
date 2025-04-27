from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from models import db, User, Graph
import pandas as pd
import json
import plotly.express as px
import plotly.io as pio
from io import StringIO


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance', 'app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/images'
db.init_app(app)


login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)
        user = User(username=username, password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        db.session.commit()
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Successfully logged in!", "success")
            return redirect(url_for('dashboard'))

        else:
            flash("Invalid username or password. Please try again.", "error")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Successfully logged out.", "success")
    return redirect(url_for('login'))

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    if request.method == 'POST':
        file = request.files['file']
        chart_type = request.form['chart_type']
        df = pd.read_csv(file)
        session['csv_data'] = df.to_json()
        return render_template('chart_setup.html', columns=df.columns, chart_type=chart_type, data_html=df.head().to_html(classes='table'))
    return render_template('dashboard.html')

@app.route('/generate-chart', methods=['POST'])
@login_required
def generate_chart():
    from io import StringIO
    df = pd.read_json(StringIO(session['csv_data']))
    x = request.form['x_col']
    y = request.form['y_col']
    color = request.form.get('color') or "blue"
    title = request.form.get('title') or "My Chart"
    chart_type = request.form['chart_type']

    if chart_type == 'bar':
        fig = px.bar(df, x=x, y=y, title=title, color_discrete_sequence=[color])
    elif chart_type == 'line':
        fig = px.line(df, x=x, y=y, title=title, color_discrete_sequence=[color])
    elif chart_type == 'scatter':
        fig = px.scatter(df, x=x, y=y, title=title, color_discrete_sequence=[color])
    else:
        fig = px.bar(df, x=x, y=y, title=title)

    fig_json = pio.to_json(fig)
    chart_html = fig.to_html(full_html=False)

    import json

    x_col = request.form['x_col']
    y_col = request.form['y_col']
    color = request.form.get('color') or None
    title = request.form.get('title') or "My Custom Chart"
    chart_type = request.form.get('chart_type')


    graph_config = {
    "x_col": x_col,
    "y_col": y_col,
    "color": color,
    "title": title
    }

    graph = Graph(
    user_id=current_user.id,
    title=title,
    chart_type=chart_type,
    config=json.dumps(graph_config)
    )

    db.session.add(graph)
    db.session.commit()

    return render_template("view_plotly.html", chart_html=chart_html, fig_json=fig_json, title=title)

@app.route('/dashboards')
@login_required
def dashboards():
    graphs = Graph.query.filter_by(user_id=current_user.id).all()

    for graph in graphs:
        try:
            graph.config = json.loads(graph.config)
        except Exception:
            graph.config = {}

    return render_template('dashboards.html', graphs=graphs)

@app.route('/view-chart/<int:chart_id>')
@login_required
def view_chart(chart_id):
    graph = Graph.query.get_or_404(chart_id)
    if graph.user_id != current_user.id:
        flash("You don't have permission to view this chart.")
        return redirect(url_for('dashboards'))

    import json
    import pandas as pd
    import plotly.express as px

    config = json.loads(graph.config)

    df = pd.read_json(StringIO(session['csv_data'])) 

    x_col = config.get('x_col')
    y_col = config.get('y_col')
    color = config.get('color')
    title = config.get('title')

    fig = px.bar(df, x=x_col, y=y_col, title=title)
    fig.update_traces(marker_color=color)

    chart_html = fig.to_html(full_html=False)

    return render_template("view_plotly.html", chart_html=chart_html, title=title)

@app.route('/edit-chart/<int:graph_id>', methods=['GET', 'POST'])
@login_required
def edit_chart(graph_id):
    graph = Graph.query.get_or_404(graph_id)

    if graph.user_id != current_user.id:
        flash("You are not authorized to edit this chart.", "error")
        return redirect(url_for('dashboards'))

    import json
    try:
        graph_config = json.loads(graph.config)
    except Exception:
        graph_config = {}

    if request.method == 'POST':
        new_title = request.form.get('title')
        new_color = request.form.get('color')

        if new_title:
            graph.title = new_title
            graph_config['title'] = new_title

        if new_color:
            graph_config['color'] = new_color

        graph.config = json.dumps(graph_config)
        db.session.commit()

        flash("Dashboard updated successfully.", "success")
        return redirect(url_for('view_chart', chart_id=graph.id))

    return render_template('edit_chart.html', graph=graph, graph_config=graph_config)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)