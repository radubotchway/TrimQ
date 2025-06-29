# File: app.py - Beautiful TrimQ Application
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField, PasswordField, IntegerField, FloatField
from wtforms.validators import DataRequired, Length, Optional
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trimq.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ============================================================================
# MODELS
# ============================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer)  # in minutes
    price = db.Column(db.Float)
    is_active = db.Column(db.Boolean, default=True)

class Barber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Customer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, assigned, completed
    barber_id = db.Column(db.Integer, db.ForeignKey('barber.id'))
    branch = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)

    service = db.relationship('Service', backref='customers')
    barber = db.relationship('Barber', backref='customers')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ============================================================================
# FORMS - Simplified for better UX
# ============================================================================

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()], render_kw={"placeholder": "Enter your username"})
    password = PasswordField('Password', validators=[DataRequired()], render_kw={"placeholder": "Enter your password"})
    submit = SubmitField('Sign In')

class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired(), Length(max=100)], render_kw={"placeholder": "Full name"})
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)], render_kw={"placeholder": "(555) 123-4567"})
    service_id = SelectField('Select Service', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Special Notes (Optional)', render_kw={"placeholder": "Any special requests or instructions...", "rows": 3})
    submit = SubmitField('Add to Queue')

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        services = Service.query.filter_by(is_active=True).order_by('name').all()
        self.service_id.choices = [(s.id, f"{s.name} ({s.duration} min • ${s.price:.0f})") for s in services]

class QuickServiceForm(FlaskForm):
    name = StringField('Service Name', validators=[DataRequired(), Length(max=100)])
    duration = IntegerField('Duration (minutes)', validators=[DataRequired()])
    price = FloatField('Price ($)', validators=[DataRequired()])
    submit = SubmitField('Add Service')

class QuickBarberForm(FlaskForm):
    name = StringField('Barber Name', validators=[DataRequired(), Length(max=100)])
    submit = SubmitField('Add Barber')

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_wait_time(customer):
    """Calculate estimated wait time for a customer"""
    if customer.status != 'waiting':
        return None
    
    # Get all customers before this one in the queue
    earlier_customers = Customer.query.filter(
        Customer.branch == customer.branch,
        Customer.status == 'waiting',
        Customer.created_at < customer.created_at
    ).order_by(Customer.created_at).all()
    
    total_wait = 0
    for c in earlier_customers:
        service = Service.query.get(c.service_id)
        if service and service.duration:
            total_wait += service.duration
    
    if total_wait == 0:
        return "Up Next!"
    elif total_wait <= 5:
        return "Very Soon"
    elif total_wait <= 15:
        return f"~{total_wait} min"
    else:
        return f"~{total_wait} min"

@app.context_processor
def inject_helpers():
    return {
        'now': datetime.now(),
        'get_wait_time': get_wait_time
    }

# ============================================================================
# ROUTES - Simplified and streamlined
# ============================================================================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('welcome.html')
    
    # Dashboard data for authenticated users
    branch = current_user.branch
    waiting_count = Customer.query.filter_by(branch=branch, status='waiting').count()
    in_progress_count = Customer.query.filter_by(branch=branch, status='assigned').count()
    completed_today = Customer.query.filter(
        Customer.branch == branch,
        Customer.status == 'completed',
        Customer.completed_at >= datetime.now().replace(hour=0, minute=0, second=0)
    ).count()
    
    return render_template('dashboard.html',
                         waiting_count=waiting_count,
                         in_progress_count=in_progress_count,
                         completed_today=completed_today)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials. Please try again.', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            phone=form.phone.data,
            service_id=form.service_id.data,
            branch=current_user.branch,
            notes=form.notes.data
        )
        db.session.add(customer)
        db.session.commit()
        flash(f'{customer.name} has been added to the queue!', 'success')
        return redirect(url_for('queue_manage'))
    return render_template('add_customer.html', form=form)

@app.route('/queue')
@login_required
def queue_manage():
    branch = current_user.branch
    waiting = Customer.query.filter_by(
        branch=branch, 
        status='waiting'
    ).order_by(Customer.created_at).all()
    
    in_progress = Customer.query.filter_by(
        branch=branch, 
        status='assigned'
    ).order_by(Customer.assigned_at).all()
    
    barbers = Barber.query.filter_by(
        branch=branch,
        is_active=True
    ).order_by(Barber.name).all()
    
    return render_template('queue.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         barbers=barbers)

@app.route('/assign/<int:customer_id>', methods=['POST'])
@login_required
def assign_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    barber_id = request.form.get('barber_id')
    
    if barber_id:
        customer.barber_id = barber_id
        customer.status = 'assigned'
        customer.assigned_at = datetime.utcnow()
        db.session.commit()
        barber = Barber.query.get(barber_id)
        flash(f'{customer.name} is now with {barber.name}', 'success')
    
    return redirect(url_for('queue_manage'))

@app.route('/complete/<int:customer_id>')
@login_required
def complete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.status = 'completed'
    customer.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f'{customer.name} is all done! ✂️', 'success')
    return redirect(url_for('queue_manage'))

@app.route('/display')
@login_required
def public_display():
    branch = current_user.branch
    waiting = Customer.query.filter_by(
        branch=branch, 
        status='waiting'
    ).order_by(Customer.created_at).all()
    
    in_progress = Customer.query.filter_by(
        branch=branch, 
        status='assigned'
    ).order_by(Customer.assigned_at).all()
    
    branch_info = Branch.query.filter_by(name=branch).first()
    return render_template('display.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         branch_info=branch_info)

@app.route('/settings')
@login_required
def settings():
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('index'))
    
    services = Service.query.order_by(Service.name).all()
    barbers = Barber.query.filter_by(branch=current_user.branch).order_by(Barber.name).all()
    
    return render_template('settings.html', services=services, barbers=barbers)

@app.route('/add_service', methods=['POST'])
@login_required
def add_service():
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('index'))
    
    name = request.form.get('name')
    duration = request.form.get('duration')
    price = request.form.get('price')
    
    if name and duration and price:
        service = Service(name=name, duration=int(duration), price=float(price))
        db.session.add(service)
        db.session.commit()
        flash(f'Service "{name}" added successfully!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/add_barber', methods=['POST'])
@login_required
def add_barber():
    if not current_user.is_admin:
        flash('Admin access required', 'error')
        return redirect(url_for('index'))
    
    name = request.form.get('name')
    if name:
        barber = Barber(name=name, branch=current_user.branch)
        db.session.add(barber)
        db.session.commit()
        flash(f'Barber "{name}" added successfully!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/toggle_service/<int:service_id>')
@login_required
def toggle_service(service_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    return redirect(url_for('settings'))

@app.route('/toggle_barber/<int:barber_id>')
@login_required
def toggle_barber(barber_id):
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    barber = Barber.query.get_or_404(barber_id)
    barber.is_active = not barber.is_active
    db.session.commit()
    return redirect(url_for('settings'))

# ============================================================================
# INITIALIZATION
# ============================================================================

def create_sample_data():
    """Create beautiful sample data"""
    
    # Create main branch
    if not Branch.query.filter_by(name='Main').first():
        branch = Branch(
            name='Main',
            address='123 Style Street, Downtown',
            phone='(555) 123-TRIM'
        )
        db.session.add(branch)
    
    # Create premium services
    services_data = [
        {'name': 'Classic Cut', 'duration': 30, 'price': 35},
        {'name': 'Beard Styling', 'duration': 20, 'price': 25},
        {'name': 'Hot Towel Shave', 'duration': 25, 'price': 30},
        {'name': 'Full Service', 'duration': 60, 'price': 55},
        {'name': 'Quick Trim', 'duration': 15, 'price': 20},
        {'name': 'Hair Wash & Style', 'duration': 25, 'price': 28}
    ]
    
    for service_data in services_data:
        if not Service.query.filter_by(name=service_data['name']).first():
            service = Service(**service_data)
            db.session.add(service)
    
    # Create skilled barbers
    barbers_data = [
        {'name': 'Alex Rodriguez', 'branch': 'Main'},
        {'name': 'Jordan Smith', 'branch': 'Main'},
        {'name': 'Casey Johnson', 'branch': 'Main'}
    ]
    
    for barber_data in barbers_data:
        if not Barber.query.filter_by(name=barber_data['name'], branch=barber_data['branch']).first():
            barber = Barber(**barber_data)
            db.session.add(barber)
    
    # Create users
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            branch='Main',
            is_admin=True
        )
        db.session.add(admin)
    
    if not User.query.filter_by(username='staff').first():
        staff = User(
            username='staff',
            password=generate_password_hash('staff123'),
            branch='Main',
            is_admin=False
        )
        db.session.add(staff)
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_data()
        print("🎯 TrimQ is ready!")
        print("📋 Login with: admin/admin123 or staff/staff123")
        print("🌐 Open: http://127.0.0.1:5000")
    
    app.run(debug=True)