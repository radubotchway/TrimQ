# File: app.py - Complete TrimQ Application
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
# FORMS
# ============================================================================

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

class CustomerForm(FlaskForm):
    name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    service_id = SelectField('Service', coerce=int, validators=[DataRequired()])
    branch = SelectField('Branch', validators=[DataRequired()])
    notes = TextAreaField('Special Instructions')
    submit = SubmitField('Add to Queue')

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        self.service_id.choices = [(s.id, f"{s.name} ({s.duration} min)") for s in Service.query.filter_by(is_active=True).order_by('name').all()]
        self.branch.choices = [(b.name, b.name) for b in Branch.query.filter_by(is_active=True).order_by('name').all()]

class ServiceForm(FlaskForm):
    name = StringField('Service Name', validators=[DataRequired(), Length(max=100)])
    duration = IntegerField('Duration (minutes)', validators=[Optional()])
    price = FloatField('Price', validators=[Optional()])
    submit = SubmitField('Add Service')

class BarberForm(FlaskForm):
    name = StringField('Barber Name', validators=[DataRequired(), Length(max=100)])
    branch = SelectField('Branch', validators=[DataRequired()])
    submit = SubmitField('Add Barber')

    def __init__(self, *args, **kwargs):
        super(BarberForm, self).__init__(*args, **kwargs)
        self.branch.choices = [(b.name, b.name) for b in Branch.query.filter_by(is_active=True).order_by('name').all()]

class BranchForm(FlaskForm):
    name = StringField('Branch Name', validators=[DataRequired(), Length(max=100)])
    address = TextAreaField('Address')
    phone = StringField('Phone Number', validators=[Optional(), Length(max=20)])
    submit = SubmitField('Add Branch')

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
        return "Now"
    
    wait_time = datetime.utcnow() + timedelta(minutes=total_wait)
    return wait_time.strftime('%H:%M')

@app.context_processor
def inject_now():
    return {'now': datetime.now()}

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    waiting_count = 0
    in_progress_count = 0
    active_barbers_count = 0
    
    if current_user.is_authenticated:
        waiting_count = Customer.query.filter_by(
            branch=current_user.branch, 
            status='waiting'
        ).count()
        
        in_progress_count = Customer.query.filter_by(
            branch=current_user.branch, 
            status='assigned'
        ).count()
        
        active_barbers_count = Barber.query.filter_by(
            branch=current_user.branch,
            is_active=True
        ).count()
    
    return render_template('index.html',
                         waiting_count=waiting_count,
                         in_progress_count=in_progress_count,
                         active_barbers_count=active_barbers_count)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page or url_for('manage_queue', branch=user.branch))
        flash('Invalid username or password', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/add_customer', methods=['GET', 'POST'])
@login_required
def add_customer():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            phone=form.phone.data,
            service_id=form.service_id.data,
            branch=form.branch.data,
            notes=form.notes.data
        )
        db.session.add(customer)
        db.session.commit()
        flash(f'Customer {customer.name} added to queue!', 'success')
        return redirect(url_for('manage_queue', branch=form.branch.data))
    return render_template('add_customer.html', form=form)

@app.route('/manage/<branch>')
@login_required
def manage_queue(branch):
    if current_user.branch != branch and not current_user.is_admin:
        flash('You can only manage your own branch queue', 'danger')
        return redirect(url_for('manage_queue', branch=current_user.branch))
    
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
    
    return render_template('manage.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         barbers=barbers,
                         branch=branch,
                         get_wait_time=get_wait_time)

@app.route('/assign/<int:customer_id>', methods=['POST'])
@login_required
def assign_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if current_user.branch != customer.branch and not current_user.is_admin:
        flash('You can only manage your own branch queue', 'danger')
        return redirect(url_for('manage_queue', branch=current_user.branch))
    
    barber_id = request.form.get('barber_id')
    if barber_id:
        customer.barber_id = barber_id
        customer.status = 'assigned'
        customer.assigned_at = datetime.utcnow()
        db.session.commit()
        flash(f'Customer {customer.name} assigned to barber!', 'success')
    return redirect(url_for('manage_queue', branch=customer.branch))

@app.route('/complete/<int:customer_id>')
@login_required
def complete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    if current_user.branch != customer.branch and not current_user.is_admin:
        flash('You can only manage your own branch queue', 'danger')
        return redirect(url_for('manage_queue', branch=current_user.branch))
    
    customer.status = 'completed'
    customer.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f'Service for {customer.name} marked as completed!', 'success')
    return redirect(url_for('manage_queue', branch=customer.branch))

@app.route('/queue/<branch>')
def public_queue(branch):
    waiting = Customer.query.filter_by(
        branch=branch, 
        status='waiting'
    ).order_by(Customer.created_at).all()
    
    in_progress = Customer.query.filter_by(
        branch=branch, 
        status='assigned'
    ).order_by(Customer.assigned_at).all()
    
    branch_info = Branch.query.filter_by(name=branch).first()
    
    return render_template('queue.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         branch=branch,
                         branch_info=branch_info,
                         get_wait_time=get_wait_time)

@app.route('/services', methods=['GET', 'POST'])
@login_required
def manage_services():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    form = ServiceForm()
    if form.validate_on_submit():
        service = Service(
            name=form.name.data,
            duration=form.duration.data,
            price=form.price.data
        )
        db.session.add(service)
        db.session.commit()
        flash(f'Service {service.name} added successfully!', 'success')
        return redirect(url_for('manage_services'))
    
    services = Service.query.order_by(Service.name).all()
    return render_template('services.html', form=form, services=services)

@app.route('/barbers', methods=['GET', 'POST'])
@login_required
def manage_barbers():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    form = BarberForm()
    if form.validate_on_submit():
        barber = Barber(
            name=form.name.data,
            branch=form.branch.data
        )
        db.session.add(barber)
        db.session.commit()
        flash(f'Barber {barber.name} added successfully!', 'success')
        return redirect(url_for('manage_barbers'))
    
    barbers = Barber.query.order_by(Barber.branch, Barber.name).all()
    return render_template('barbers.html', form=form, barbers=barbers)

@app.route('/branches', methods=['GET', 'POST'])
@login_required
def manage_branches():
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    form = BranchForm()
    if form.validate_on_submit():
        branch = Branch(
            name=form.name.data,
            address=form.address.data,
            phone=form.phone.data
        )
        db.session.add(branch)
        db.session.commit()
        flash(f'Branch {branch.name} added successfully!', 'success')
        return redirect(url_for('manage_branches'))
    
    branches = Branch.query.order_by(Branch.name).all()
    return render_template('branches.html', form=form, branches=branches)

@app.route('/toggle_service/<int:service_id>', methods=['POST'])
@login_required
def toggle_service(service_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    flash(f'Service {service.name} {"activated" if service.is_active else "deactivated"}', 'success')
    return redirect(url_for('manage_services'))

@app.route('/toggle_barber/<int:barber_id>', methods=['POST'])
@login_required
def toggle_barber(barber_id):
    if not current_user.is_admin:
        flash('Admin access required', 'danger')
        return redirect(url_for('index'))
    
    barber = Barber.query.get_or_404(barber_id)
    barber.is_active = not barber.is_active
    db.session.commit()
    flash(f'Barber {barber.name} {"activated" if barber.is_active else "deactivated"}', 'success')
    return redirect(url_for('manage_barbers'))

# ============================================================================
# INITIALIZATION
# ============================================================================

def create_sample_data():
    """Create sample data for testing"""
    
    # Create branches
    branches_data = [
        {'name': 'Main', 'address': '123 Main Street', 'phone': '555-0100'},
        {'name': 'Downtown', 'address': '456 Downtown Ave', 'phone': '555-0200'},
        {'name': 'Uptown', 'address': '789 Uptown Blvd', 'phone': '555-0300'}
    ]
    
    for branch_data in branches_data:
        if not Branch.query.filter_by(name=branch_data['name']).first():
            branch = Branch(**branch_data)
            db.session.add(branch)
    
    # Create services
    services_data = [
        {'name': 'Haircut', 'duration': 30, 'price': 25.00},
        {'name': 'Beard Trim', 'duration': 15, 'price': 15.00},
        {'name': 'Hair Wash', 'duration': 10, 'price': 10.00},
        {'name': 'Full Service', 'duration': 45, 'price': 35.00},
        {'name': 'Shave', 'duration': 20, 'price': 20.00}
    ]
    
    for service_data in services_data:
        if not Service.query.filter_by(name=service_data['name']).first():
            service = Service(**service_data)
            db.session.add(service)
    
    # Create barbers
    barbers_data = [
        {'name': 'John Smith', 'branch': 'Main'},
        {'name': 'Mike Johnson', 'branch': 'Main'},
        {'name': 'Sarah Wilson', 'branch': 'Downtown'},
        {'name': 'David Brown', 'branch': 'Downtown'},
        {'name': 'Lisa Davis', 'branch': 'Uptown'}
    ]
    
    for barber_data in barbers_data:
        if not Barber.query.filter_by(name=barber_data['name'], branch=barber_data['branch']).first():
            barber = Barber(**barber_data)
            db.session.add(barber)
    
    # Create admin user
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            password=generate_password_hash('admin123'),
            branch='Main',
            is_admin=True
        )
        db.session.add(admin)
    
    # Create branch managers
    managers_data = [
        {'username': 'main_manager', 'password': 'password123', 'branch': 'Main'},
        {'username': 'downtown_manager', 'password': 'password123', 'branch': 'Downtown'},
        {'username': 'uptown_manager', 'password': 'password123', 'branch': 'Uptown'}
    ]
    
    for manager_data in managers_data:
        if not User.query.filter_by(username=manager_data['username']).first():
            user = User(
                username=manager_data['username'],
                password=generate_password_hash(manager_data['password']),
                branch=manager_data['branch'],
                is_admin=False
            )
            db.session.add(user)
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_data()
        print("Database initialized with sample data!")
        print("\nLogin credentials:")
        print("Admin: admin / admin123")
        print("Main Manager: main_manager / password123")
        print("Downtown Manager: downtown_manager / password123")
        print("Uptown Manager: uptown_manager / password123")
    
    app.run(debug=True)