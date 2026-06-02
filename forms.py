from flask_wtf import Form
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, EqualTo, Length
from wtforms import TextAreaField

# Set your classes here.


class RegisterForm(Form):
    name = StringField(
        'Username', validators=[DataRequired(), Length(min=6, max=25)]
    )
    email = StringField(
        'Email', validators=[DataRequired(), Length(min=6, max=40)]
    )
    password = PasswordField(
        'Password', validators=[DataRequired(), Length(min=6, max=40)]
    )
    confirm = PasswordField(
        'Repeat Password',
        [DataRequired(),
        EqualTo('password', message='Passwords must match')]
    )


class LoginForm(Form):
    name = StringField('Username', [DataRequired()])
    password = PasswordField('Password', [DataRequired()])


class ForgotForm(Form):
    email = StringField(
        'Email', validators=[DataRequired(), Length(min=6, max=40)]
    )


class HomeworkForm(Form):
    subject = StringField('Subject', validators=[DataRequired(), Length(max=100)])
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    notes = TextAreaField('Notes')
    start_date = StringField('Start Date (YYYY-MM-DD)')
    due_date = StringField('Due Date (YYYY-MM-DD)')
    priority = StringField('Priority (low/medium/high)')


class ExamForm(Form):
    subject = StringField('Subject', validators=[DataRequired(), Length(max=100)])
    title = StringField('Title', validators=[DataRequired(), Length(max=200)])
    exam_date = StringField('Exam Date (YYYY-MM-DD)', validators=[DataRequired()])
    exam_time = StringField('Exam Time (HH:MM)', validators=[Length(max=10)])
    location = StringField('Location', validators=[Length(max=255)])
    notes = TextAreaField('Notes')
