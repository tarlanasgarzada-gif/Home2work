#----------------------------------------------------------------------------#
# Imports
#----------------------------------------------------------------------------#

from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
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
    exams = db.relationship('Exam', backref='user', lazy=True)

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


# Exam model to store exams per user
class Exam(db.Model):
    __tablename__ = 'exams'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    exam_time = db.Column(db.String(10))  # Format: HH:MM
    location = db.Column(db.String(255))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

#----------------------------------------------------------------------------#
# Helpers.
#----------------------------------------------------------------------------#

def _sort_homeworks_by_priority(homeworks):
    priority_rank = {'high': 0, 'medium': 1, 'low': 2}
    return sorted(
        homeworks,
        key=lambda hw: (
            priority_rank.get((hw.priority or 'medium').lower(), 1),
            hw.due_date or date.max,
            hw.created_at or datetime.max,
        )
    )


#----------------------------------------------------------------------------#
# Controllers.
#----------------------------------------------------------------------------#

@app.route('/')
def home():
    pending_homeworks = []
    finished_homeworks = []
    stats = {
        'total_tasks': 0,
        'tasks_with_deadline': 0,
        'remaining_tasks': 0,
    }
    if current_user.is_authenticated:
        homeworks = Homework.query.filter_by(user_id=current_user.id).all()
        homeworks = _sort_homeworks_by_priority(homeworks)
        pending_homeworks = [hw for hw in homeworks if hw.status == 'Pending']
        finished_homeworks = [hw for hw in homeworks if hw.status != 'Pending']
        
        # Calculate statistics
        stats['total_tasks'] = len(homeworks)
        stats['tasks_with_deadline'] = sum(1 for hw in homeworks if hw.due_date)
        stats['remaining_tasks'] = len(pending_homeworks)
    return render_template(
        'pages/placeholder.home.html',
        pending_homeworks=pending_homeworks,
        finished_homeworks=finished_homeworks,
        stats=stats,
    )


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
    homeworks_list = Homework.query.filter_by(user_id=current_user.id).all()
    homeworks_list = _sort_homeworks_by_priority(homeworks_list)
    pending_homeworks = [hw for hw in homeworks_list if hw.status == 'Pending']
    finished_homeworks = [hw for hw in homeworks_list if hw.status != 'Pending']
    return render_template(
        'pages/placeholder.homeworks.html',
        form=form,
        pending_homeworks=pending_homeworks,
        finished_homeworks=finished_homeworks,
    )


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


@app.route('/homeworks/<int:hw_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_homework(hw_id):
    hw = Homework.query.get_or_404(hw_id)
    if hw.user_id != current_user.id:
        abort(403)
    
    form = HomeworkForm(request.form)
    
    if request.method == 'POST' and form.validate():
        hw.subject = form.subject.data
        hw.title = form.title.data
        hw.notes = form.notes.data
        hw.priority = form.priority.data or 'medium'
        
        try:
            if form.start_date.data:
                hw.start_date = datetime.strptime(form.start_date.data, '%Y-%m-%d').date()
            else:
                hw.start_date = None
        except Exception:
            hw.start_date = None
        
        try:
            if form.due_date.data:
                hw.due_date = datetime.strptime(form.due_date.data, '%Y-%m-%d').date()
            else:
                hw.due_date = None
        except Exception:
            hw.due_date = None
        
        db.session.commit()
        flash('Homework updated.', 'success')
        return redirect(url_for('home'))
    
    # Pre-populate form with existing data
    if request.method == 'GET':
        form.subject.data = hw.subject
        form.title.data = hw.title
        form.notes.data = hw.notes
        form.priority.data = hw.priority or 'medium'
        if hw.start_date:
            form.start_date.data = hw.start_date.strftime('%Y-%m-%d')
        if hw.due_date:
            form.due_date.data = hw.due_date.strftime('%Y-%m-%d')
    
    return render_template('pages/edit_homework.html', form=form, homework=hw)


@app.route('/homeworks/<int:hw_id>/delete', methods=['POST'])
@login_required
def delete_homework(hw_id):
    hw = Homework.query.get_or_404(hw_id)
    if hw.user_id != current_user.id:
        abort(403)
    db.session.delete(hw)
    db.session.commit()
    flash('Homework deleted.', 'success')
    return redirect(url_for('home'))


@app.route('/exams', methods=['GET', 'POST'])
@login_required
def upcoming_exams():
    form = ExamForm(request.form)
    
    if request.method == 'POST' and form.validate():
        try:
            exam_date = datetime.strptime(form.exam_date.data, '%Y-%m-%d').date()
        except Exception:
            flash('Invalid exam date format.', 'danger')
            exam_date = None
        
        if exam_date:
            exam = Exam(
                user_id=current_user.id,
                subject=form.subject.data,
                title=form.title.data,
                exam_date=exam_date,
                exam_time=form.exam_time.data,
                location=form.location.data,
                notes=form.notes.data,
            )
            db.session.add(exam)
            db.session.commit()
            flash('Exam added.', 'success')
            return redirect(url_for('upcoming_exams'))
    
    # Fetch all upcoming exams sorted by date
    exams = Exam.query.filter_by(user_id=current_user.id).order_by(Exam.exam_date.asc()).all()
    
    return render_template('pages/upcoming_exams.html', form=form, exams=exams)


@app.route('/timeline')
@login_required
def timeline():
    from datetime import timedelta
    
    today = date.today()
    end_of_month = today.replace(day=1) + timedelta(days=32)
    end_of_month = end_of_month.replace(day=1) - timedelta(days=1)
    
    # Get exams for the next month
    upcoming_exams = Exam.query.filter_by(user_id=current_user.id).filter(
        Exam.exam_date >= today,
        Exam.exam_date <= end_of_month
    ).order_by(Exam.exam_date.asc()).all()
    
    # Group exams by date
    timeline_data = {}
    for exam in upcoming_exams:
        exam_date_str = exam.exam_date.strftime('%Y-%m-%d')
        if exam_date_str not in timeline_data:
            timeline_data[exam_date_str] = []
        timeline_data[exam_date_str].append(exam)
    
    return render_template('pages/timeline.html', timeline_data=timeline_data, today=today, end_of_month=end_of_month)


@app.route('/exams/<int:exam_id>/delete', methods=['POST'])
@login_required
def delete_exam(exam_id):
    exam = Exam.query.get_or_404(exam_id)
    if exam.user_id != current_user.id:
        abort(403)
    db.session.delete(exam)
    db.session.commit()
    flash('Exam deleted.', 'success')
    return redirect(url_for('upcoming_exams'))


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