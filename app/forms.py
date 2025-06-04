from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField, PasswordField
from wtforms.validators import DataRequired, Length, Email
from app.models import Barber, Service, Branch

class CustomerForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    service_id = SelectField('Service', coerce=int, validators=[DataRequired()])
    branch = SelectField('Branch', validators=[DataRequired()])
    notes = TextAreaField('Special Instructions')
    submit = SubmitField('Add to Queue')

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        self.service_id.choices = [(s.id, s.name) for s in Service.query.filter_by(is_active=True).order_by('name').all()]
        self.branch.choices = [(b.name, b.name) for b in Branch.query.filter_by(is_active=True).order_by('name').all()]

class BarberForm(FlaskForm):
    name = StringField('Barber Name', validators=[DataRequired(), Length(max=100)])
    branch = SelectField('Branch', validators=[DataRequired()])
    submit = SubmitField('Add Barber')

    def __init__(self, *args, **kwargs):
        super(BarberForm, self).__init__(*args, **kwargs)
        self.branch.choices = [(b.name, b.name) for b in Branch.query.filter_by(is_active=True).order_by('name').all()]

class ServiceForm(FlaskForm):
    name = StringField('Service Name', validators=[DataRequired(), Length(max=100)])
    duration = StringField('Duration (minutes)')
    price = StringField('Price')
    submit = SubmitField('Add Service')

class BranchForm(FlaskForm):
    name = StringField('Branch Name', validators=[DataRequired(), Length(max=100)])
    address = TextAreaField('Address')
    phone = StringField('Phone Number', validators=[Length(max=20)])
    submit = SubmitField('Add Branch')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')