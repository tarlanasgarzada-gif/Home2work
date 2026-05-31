#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
from logging import Formatter, FileHandler
from forms import * # Keeps your existing forms layout intact
import os

#----------------------------------------------------------------------------#
# App Config.
#----------------------------------------------------------------------------#

app = Flask(__name__)
app.config.from_object('config')

# SQLite Database configurations
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure a secret key exists for session management and CSRF tokens
if not app.config.get('SECRET_KEY'):
    app.config['SECRET_KEY'] = 'a-fallback-secret-key-change-this'

db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

#----------------------------------------------------------------------------#
# Models.
#----------------------------------------------------------------------------#

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    homeworks = db.relationship('Homework', backref='user', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Homework model to store assignments per user
class Homework(db.Model):
    __tablename__ = 'homeworks'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text)
    start_date = db.Column(db.Date)
    due_date = db.Column(db.Date)
    priority = db.Column(db.String(20))
    status = db.Column(db.String(50), default='Pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def home():
    homeworks = None
    if current_user.is_authenticated:
        homeworks = Homework.query.filter_by(user_id=current_user.id).order_by(Homework.due_date.asc()).all()
    return render_template('pages/placeholder.home.html', homeworks=homeworks)


@app.route('/about')
def about():
    return render_template('pages/placeholder.about.html')

@app.route('/homeworks', methods=['GET', 'POST'])
@login_required
def homeworks():
    form = HomeworkForm(request.form)

    if request.method == 'POST' and form.validate():
        # parse optional dates in YYYY-MM-DD format
        start = None
        due = None
        try:
            if form.start_date.data:
                start = datetime.strptime(form.start_date.data, '%Y-%m-%d').date()
        except Exception:
            start = None
        try:
            if form.due_date.data:
                due = datetime.strptime(form.due_date.data, '%Y-%m-%d').date()
        except Exception:
            due = None

        hw = Homework(
            user_id=current_user.id,
            subject=form.subject.data,
            title=form.title.data,
            notes=form.notes.data,
            start_date=start,
            due_date=due,
            priority=form.priority.data or 'medium'
        )
        db.session.add(hw)
        db.session.commit()
        flash('Homework created.', 'success')
        return redirect(url_for('home'))

    # GET: show form and user's homeworks
    homeworks_list = Homework.query.filter_by(user_id=current_user.id).order_by(Homework.due_date.asc()).all()
    return render_template('pages/placeholder.homeworks.html', form=form, homeworks=homeworks_list)


@app.route('/homeworks/<int:hw_id>/complete', methods=['POST'])
@login_required
def complete_homework(hw_id):
    hw = Homework.query.get_or_404(hw_id)
    if hw.user_id != current_user.id:
        abort(403)
    hw.status = 'Finished'
    db.session.commit()
    flash('Homework marked as finished.', 'success')
    return redirect(url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = LoginForm(request.form)
    
    # Triggered when a user submits the login form
    if request.method == 'POST' and form.validate():
        user = User.query.filter_by(name=form.name.data).first()
        
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password.', 'danger')
            
    return render_template('forms/login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RegisterForm(request.form)
    
    # Triggered when a user submits the registration form
    if request.method == 'POST' and form.validate():
        # Check if user already exists
        existing_user = User.query.filter((User.name == form.name.data) | (User.email == form.email.data)).first()
        if existing_user:
            flash('Username or Email already exists.', 'warning')
            return render_template('forms/register.html', form=form)
        
        # Hash password and save user
        hashed_pw = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        new_user = User(name=form.name.data, email=form.email.data, password=hashed_pw)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration complete! Please log in.', 'success')
        return redirect(url_for('login'))
        
    return render_template('forms/register.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    form = ForgotForm(request.form)
    return render_template('forms/forgot.html', form=form)

# Error handlers.

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback() # Safely roll back failed DB sessions
    return render_template('errors/500.html'), 500


@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

if not app.debug:
    file_handler = FileHandler('error.log')
    file_handler.setFormatter(
        Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    )
    app.logger.setLevel(logging.INFO)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('errors')

#----------------------------------------------------------------------------#
# Launch & Database Generation
#----------------------------------------------------------------------------#

# Create SQLite tables inside application context if they don't exist yet
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)