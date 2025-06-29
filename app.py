# File: app.py - Multi-Branch Franchise TrimQ Application
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
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trimq_franchise.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Branch configuration
BRANCHES = {
    'main': {'name': 'Main Branch', 'address': '123 Oxford Street, Osu', 'phone': '0302-123-456'},
    'downtown': {'name': 'Downtown Branch', 'address': '45 Kwame Nkrumah Ave, Adabraka', 'phone': '0302-789-012'},
    'uptown': {'name': 'East Legon Branch', 'address': '78 Liberation Road, East Legon', 'phone': '0302-345-678'}
}

# ============================================================================
# MODELS
# ============================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='staff')  # master_admin, branch_admin, staff
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_master_admin(self):
        return self.role == 'master_admin'
    
    def is_branch_admin(self):
        return self.role == 'branch_admin'
    
    def can_manage_branch(self, branch_name):
        return self.is_master_admin() or (self.is_branch_admin() and self.branch == branch_name)

class Branch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    address = db.Column(db.Text)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)

class Service(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer)  # in minutes
    price = db.Column(db.Float)  # in cedis
    is_active = db.Column(db.Boolean, default=True)

class Barber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    hired_date = db.Column(db.Date, default=datetime.utcnow)

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
    username = StringField('Username', validators=[DataRequired()], render_kw={"placeholder": "Enter your username"})
    password = PasswordField('Password', validators=[DataRequired()], render_kw={"placeholder": "Enter your password"})
    submit = SubmitField('Sign In')

class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired(), Length(max=100)], render_kw={"placeholder": "Full name"})
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)], render_kw={"placeholder": "0244-123-456"})
    service_id = SelectField('Select Service', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Special Notes (Optional)', render_kw={"placeholder": "Any special requests or instructions...", "rows": 3})
    submit = SubmitField('Add to Queue')

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        services = Service.query.filter_by(is_active=True).order_by('name').all()
        self.service_id.choices = [(s.id, f"{s.name} ({s.duration} min • GH₵{s.price:.0f})") for s in services]

class ServiceForm(FlaskForm):
    name = StringField('Service Name', validators=[DataRequired(), Length(max=100)])
    duration = IntegerField('Duration (minutes)', validators=[DataRequired()])
    price = FloatField('Price (GH₵)', validators=[DataRequired()])
    submit = SubmitField('Add Service')

class BarberForm(FlaskForm):
    name = StringField('Barber Name', validators=[DataRequired(), Length(max=100)])
    branch = SelectField('Branch', validators=[DataRequired()])
    submit = SubmitField('Add Barber')

    def __init__(self, user, *args, **kwargs):
        super(BarberForm, self).__init__(*args, **kwargs)
        if user.is_master_admin():
            # Master admin can assign to any branch
            self.branch.choices = [(code, info['name']) for code, info in BRANCHES.items()]
        else:
            # Branch admin can only assign to their branch
            self.branch.choices = [(user.branch, BRANCHES[user.branch]['name'])]

class StaffForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    role = SelectField('Role', choices=[('staff', 'Staff'), ('branch_admin', 'Branch Admin')], validators=[DataRequired()])
    branch = SelectField('Branch', validators=[DataRequired()])
    submit = SubmitField('Add Staff Member')

    def __init__(self, user, *args, **kwargs):
        super(StaffForm, self).__init__(*args, **kwargs)
        if user.is_master_admin():
            self.branch.choices = [(code, info['name']) for code, info in BRANCHES.items()]
        else:
            self.branch.choices = [(user.branch, BRANCHES[user.branch]['name'])]
            self.role.choices = [('staff', 'Staff')]  # Branch admin can only create staff

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_wait_time(customer):
    """Calculate estimated wait time for a customer"""
    if customer.status != 'waiting':
        return None
    
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

def get_branch_stats(branch_code):
    """Get statistics for a specific branch"""
    waiting = Customer.query.filter_by(branch=branch_code, status='waiting').count()
    in_progress = Customer.query.filter_by(branch=branch_code, status='assigned').count()
    completed_today = Customer.query.filter(
        Customer.branch == branch_code,
        Customer.status == 'completed',
        Customer.completed_at >= datetime.now().replace(hour=0, minute=0, second=0)
    ).count()
    active_barbers = Barber.query.filter_by(branch=branch_code, is_active=True).count()
    
    return {
        'waiting': waiting,
        'in_progress': in_progress,
        'completed_today': completed_today,
        'active_barbers': active_barbers
    }

def get_franchise_stats():
    """Get statistics for entire franchise"""
    total_waiting = Customer.query.filter_by(status='waiting').count()
    total_in_progress = Customer.query.filter_by(status='assigned').count()
    total_completed_today = Customer.query.filter(
        Customer.status == 'completed',
        Customer.completed_at >= datetime.now().replace(hour=0, minute=0, second=0)
    ).count()
    total_barbers = Barber.query.filter_by(is_active=True).count()
    
    return {
        'total_waiting': total_waiting,
        'total_in_progress': total_in_progress,
        'total_completed_today': total_completed_today,
        'total_barbers': total_barbers
    }

@app.context_processor
def inject_helpers():
    return {
        'now': datetime.now(),
        'get_wait_time': get_wait_time,
        'BRANCHES': BRANCHES
    }

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('welcome.html')
    
    if current_user.is_master_admin():
        # Master admin sees franchise overview
        franchise_stats = get_franchise_stats()
        branch_stats = {}
        for code in BRANCHES.keys():
            branch_stats[code] = get_branch_stats(code)
        
        return render_template('master_dashboard.html',
                             franchise_stats=franchise_stats,
                             branch_stats=branch_stats)
    else:
        # Branch admin/staff see their branch
        branch_stats = get_branch_stats(current_user.branch)
        return render_template('dashboard.html', **branch_stats)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data, is_active=True).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            role_name = 'Master Admin' if user.is_master_admin() else 'Branch Admin' if user.is_branch_admin() else 'Staff'
            flash(f'Welcome back, {role_name}!', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials or account disabled.', 'error')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/branch/<branch_code>')
@login_required
def branch_view(branch_code):
    if not current_user.can_manage_branch(branch_code):
        flash('Access denied to this branch.', 'error')
        return redirect(url_for('index'))
    
    branch_stats = get_branch_stats(branch_code)
    branch_info = BRANCHES.get(branch_code, {})
    
    return render_template('branch_dashboard.html',
                         branch_code=branch_code,
                         branch_info=branch_info,
                         **branch_stats)

@app.route('/add/<branch_code>', methods=['GET', 'POST'])
@login_required
def add_customer(branch_code=None):
    # Default to user's branch if not specified
    if not branch_code:
        branch_code = current_user.branch
    
    if not current_user.can_manage_branch(branch_code):
        flash('Access denied to this branch.', 'error')
        return redirect(url_for('index'))
    
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(
            name=form.name.data,
            phone=form.phone.data,
            service_id=form.service_id.data,
            branch=branch_code,
            notes=form.notes.data
        )
        db.session.add(customer)
        db.session.commit()
        flash(f'{customer.name} has been added to the {BRANCHES[branch_code]["name"]} queue!', 'success')
        return redirect(url_for('queue_manage', branch_code=branch_code))
    
    return render_template('add_customer.html', form=form, branch_code=branch_code, branch_info=BRANCHES[branch_code])

@app.route('/queue/<branch_code>')
@login_required
def queue_manage(branch_code):
    if not current_user.can_manage_branch(branch_code):
        flash('Access denied to this branch.', 'error')
        return redirect(url_for('index'))
    
    waiting = Customer.query.filter_by(
        branch=branch_code, 
        status='waiting'
    ).order_by(Customer.created_at).all()
    
    in_progress = Customer.query.filter_by(
        branch=branch_code, 
        status='assigned'
    ).order_by(Customer.assigned_at).all()
    
    barbers = Barber.query.filter_by(
        branch=branch_code,
        is_active=True
    ).order_by(Barber.name).all()
    
    return render_template('queue.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         barbers=barbers,
                         branch_code=branch_code,
                         branch_info=BRANCHES[branch_code])

@app.route('/assign/<int:customer_id>', methods=['POST'])
@login_required
def assign_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    if not current_user.can_manage_branch(customer.branch):
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    barber_id = request.form.get('barber_id')
    if barber_id:
        customer.barber_id = barber_id
        customer.status = 'assigned'
        customer.assigned_at = datetime.utcnow()
        db.session.commit()
        barber = Barber.query.get(barber_id)
        flash(f'{customer.name} is now with {barber.name}', 'success')
    
    return redirect(url_for('queue_manage', branch_code=customer.branch))

@app.route('/complete/<int:customer_id>')
@login_required
def complete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    if not current_user.can_manage_branch(customer.branch):
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    customer.status = 'completed'
    customer.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f'{customer.name} is all done! ✂️', 'success')
    return redirect(url_for('queue_manage', branch_code=customer.branch))

@app.route('/display/<branch_code>')
def public_display(branch_code):
    waiting = Customer.query.filter_by(
        branch=branch_code, 
        status='waiting'
    ).order_by(Customer.created_at).all()
    
    in_progress = Customer.query.filter_by(
        branch=branch_code, 
        status='assigned'
    ).order_by(Customer.assigned_at).all()
    
    branch_info = BRANCHES.get(branch_code, {})
    return render_template('display.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         branch_code=branch_code,
                         branch_info=branch_info)

@app.route('/settings')
@login_required
def settings():
    if not (current_user.is_master_admin() or current_user.is_branch_admin()):
        flash('Admin access required', 'error')
        return redirect(url_for('index'))
    
    services = Service.query.order_by(Service.name).all()
    
    if current_user.is_master_admin():
        barbers = Barber.query.order_by(Barber.branch, Barber.name).all()
        staff = User.query.filter(User.role != 'master_admin').order_by(User.branch, User.username).all()
        branches = Branch.query.order_by(Branch.name).all()
    else:
        barbers = Barber.query.filter_by(branch=current_user.branch).order_by(Barber.name).all()
        staff = User.query.filter_by(branch=current_user.branch).filter(User.role != 'master_admin').order_by(User.username).all()
        branches = []
    
    return render_template('settings.html', services=services, barbers=barbers, staff=staff, branches=branches)

@app.route('/add_service', methods=['POST'])
@login_required
def add_service():
    if not (current_user.is_master_admin() or current_user.is_branch_admin()):
        flash('Admin access required', 'error')
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
        flash(f'Service "{service.name}" added successfully!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/add_barber', methods=['POST'])
@login_required
def add_barber():
    if not (current_user.is_master_admin() or current_user.is_branch_admin()):
        flash('Admin access required', 'error')
        return redirect(url_for('index'))
    
    name = request.form.get('name')
    branch = request.form.get('branch')
    
    if not name or not branch:
        flash('Name and branch are required', 'error')
        return redirect(url_for('settings'))
    
    # Branch admin can only add to their branch
    if not current_user.is_master_admin() and branch != current_user.branch:
        flash('You can only add barbers to your own branch', 'error')
        return redirect(url_for('settings'))
    
    barber = Barber(name=name, branch=branch)
    db.session.add(barber)
    db.session.commit()
    flash(f'Barber "{barber.name}" added successfully!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/add_branch', methods=['POST'])
@login_required
def add_branch():
    if not current_user.is_master_admin():
        flash('Only master admin can add branches', 'error')
        return redirect(url_for('settings'))
    
    code = request.form.get('code', '').lower().strip()
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if not code or not name or not address:
        flash('Code, name, and address are required', 'error')
        return redirect(url_for('settings'))
    
    # Check if branch code already exists
    if Branch.query.filter_by(code=code).first():
        flash('Branch code already exists', 'error')
        return redirect(url_for('settings'))
    
    branch = Branch(code=code, name=name, address=address, phone=phone)
    db.session.add(branch)
    db.session.commit()
    
    # Update BRANCHES dictionary dynamically
    BRANCHES[code] = {'name': name, 'address': address, 'phone': phone}
    
    flash(f'Branch "{name}" added successfully!', 'success')
    return redirect(url_for('settings'))

@app.route('/toggle_branch/<int:branch_id>')
@login_required
def toggle_branch(branch_id):
    if not current_user.is_master_admin():
        flash('Only master admin can manage branches', 'error')
        return redirect(url_for('settings'))
    
    branch = Branch.query.get_or_404(branch_id)
    branch.is_active = not branch.is_active
    db.session.commit()
    
    flash(f'Branch "{branch.name}" {"activated" if branch.is_active else "deactivated"}', 'success')
    return redirect(url_for('settings'))

@app.route('/delete_barber/<int:barber_id>')
@login_required
def delete_barber(barber_id):
    if not current_user.is_master_admin():
        flash('Only master admin can delete barbers', 'error')
        return redirect(url_for('settings'))
    
    barber = Barber.query.get_or_404(barber_id)
    
    # Check if barber has active customers
    active_customers = Customer.query.filter_by(barber_id=barber.id, status='assigned').count()
    if active_customers > 0:
        flash(f'Cannot delete {barber.name} - they have {active_customers} active customer(s)', 'error')
        return redirect(url_for('settings'))
    
    name = barber.name
    db.session.delete(barber)
    db.session.commit()
    
    flash(f'Barber "{name}" deleted successfully', 'success')
    return redirect(url_for('settings'))

@app.route('/delete_staff/<int:staff_id>')
@login_required
def delete_staff(staff_id):
    if not current_user.is_master_admin():
        flash('Only master admin can delete staff', 'error')
        return redirect(url_for('settings'))
    
    staff = User.query.get_or_404(staff_id)
    
    # Cannot delete master admin
    if staff.is_master_admin():
        flash('Cannot delete master admin account', 'error')
        return redirect(url_for('settings'))
    
    username = staff.username
    db.session.delete(staff)
    db.session.commit()
    
    flash(f'Staff member "{username}" deleted successfully', 'success')
    return redirect(url_for('settings'))

@app.route('/add_staff', methods=['POST'])
@login_required
def add_staff():
    if not (current_user.is_master_admin() or current_user.is_branch_admin()):
        flash('Admin access required', 'error')
        return redirect(url_for('index'))
    
    form = StaffForm(current_user)
    if form.validate_on_submit():
        # Check if username already exists
        if User.query.filter_by(username=form.username.data).first():
            flash('Username already exists!', 'error')
            return redirect(url_for('settings'))
        
        user = User(
            username=form.username.data,
            password=generate_password_hash(form.password.data),
            role=form.role.data,
            branch=form.branch.data
        )
        db.session.add(user)
        db.session.commit()
        flash(f'Staff member "{user.username}" added successfully!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/toggle_service/<int:service_id>')
@login_required
def toggle_service(service_id):
    if not (current_user.is_master_admin() or current_user.is_branch_admin()):
        return redirect(url_for('index'))
    
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    return redirect(url_for('settings'))

@app.route('/toggle_barber/<int:barber_id>')
@login_required
def toggle_barber(barber_id):
    if not (current_user.is_master_admin() or current_user.is_branch_admin()):
        return redirect(url_for('index'))
    
    barber = Barber.query.get_or_404(barber_id)
    
    # Branch admin can only toggle barbers in their branch
    if not current_user.can_manage_branch(barber.branch):
        flash('Access denied.', 'error')
        return redirect(url_for('settings'))
    
    barber.is_active = not barber.is_active
    db.session.commit()
    return redirect(url_for('settings'))

@app.route('/toggle_staff/<int:staff_id>')
@login_required
def toggle_staff(staff_id):
    if not (current_user.is_master_admin() or current_user.is_branch_admin()):
        return redirect(url_for('index'))
    
    staff = User.query.get_or_404(staff_id)
    
    # Branch admin can only toggle staff in their branch
    if not current_user.can_manage_branch(staff.branch):
        flash('Access denied.', 'error')
        return redirect(url_for('settings'))
    
    # Can't deactivate master admin
    if staff.is_master_admin():
        flash('Cannot deactivate master admin.', 'error')
        return redirect(url_for('settings'))
    
    staff.is_active = not staff.is_active
    db.session.commit()
    return redirect(url_for('settings'))

# ============================================================================
# INITIALIZATION
# ============================================================================

def create_sample_data():
    """Create sample data for the franchise"""
    
    # Create branches in database
    for code, info in BRANCHES.items():
        if not Branch.query.filter_by(code=code).first():
            branch = Branch(
                name=info['name'],
                code=code,
                address=info['address'],
                phone=info['phone']
            )
            db.session.add(branch)
    
    # Create services with Ghanaian Cedis pricing
    services_data = [
        {'name': 'Classic Cut', 'duration': 30, 'price': 50},
        {'name': 'Beard Styling', 'duration': 20, 'price': 35},
        {'name': 'Hot Towel Shave', 'duration': 25, 'price': 40},
        {'name': 'Full Service', 'duration': 60, 'price': 80},
        {'name': 'Quick Trim', 'duration': 15, 'price': 25},
        {'name': 'Hair Wash & Style', 'duration': 25, 'price': 35},
        {'name': 'Mustache Trim', 'duration': 10, 'price': 15},
        {'name': 'Eyebrow Trim', 'duration': 15, 'price': 20}
    ]
    
    for service_data in services_data:
        if not Service.query.filter_by(name=service_data['name']).first():
            service = Service(**service_data)
            db.session.add(service)
    
    # Create barbers for each branch
    barbers_data = [
        # Main Branch
        {'name': 'Kwame Asante', 'branch': 'main'},
        {'name': 'Kofi Mensah', 'branch': 'main'},
        {'name': 'Emmanuel Owusu', 'branch': 'main'},
        
        # Downtown Branch
        {'name': 'Yaw Boateng', 'branch': 'downtown'},
        {'name': 'Samuel Osei', 'branch': 'downtown'},
        {'name': 'Daniel Nkrumah', 'branch': 'downtown'},
        
        # East Legon Branch
        {'name': 'Isaac Adjei', 'branch': 'uptown'},
        {'name': 'Prince Agyemang', 'branch': 'uptown'},
        {'name': 'Michael Tettey', 'branch': 'uptown'}
    ]
    
    for barber_data in barbers_data:
        if not Barber.query.filter_by(name=barber_data['name'], branch=barber_data['branch']).first():
            barber = Barber(**barber_data)
            db.session.add(barber)
    
    # Create user accounts
    users_data = [
        # Master Admin (Franchise Owner)
        {'username': 'master_admin', 'password': 'master123', 'role': 'master_admin', 'branch': 'main'},
        
        # Branch Admins
        {'username': 'main_admin', 'password': 'main123', 'role': 'branch_admin', 'branch': 'main'},
        {'username': 'downtown_admin', 'password': 'downtown123', 'role': 'branch_admin', 'branch': 'downtown'},
        {'username': 'uptown_admin', 'password': 'uptown123', 'role': 'branch_admin', 'branch': 'uptown'},
        
        # Staff members
        {'username': 'main_staff', 'password': 'staff123', 'role': 'staff', 'branch': 'main'},
        {'username': 'downtown_staff', 'password': 'staff123', 'role': 'staff', 'branch': 'downtown'},
        {'username': 'uptown_staff', 'password': 'staff123', 'role': 'staff', 'branch': 'uptown'},
    ]
    
    for user_data in users_data:
        if not User.query.filter_by(username=user_data['username']).first():
            user = User(
                username=user_data['username'],
                password=generate_password_hash(user_data['password']),
                role=user_data['role'],
                branch=user_data['branch']
            )
            db.session.add(user)
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_data()
        print("🏢 TrimQ Franchise System Ready!")
        print("\n📋 Login Credentials:")
        print("👑 Master Admin: master_admin / master123")
        print("🏪 Main Branch Admin: main_admin / main123")
        print("🏪 Downtown Branch Admin: downtown_admin / downtown123")
        print("🏪 East Legon Branch Admin: uptown_admin / uptown123")
        print("👤 Staff: main_staff, downtown_staff, uptown_staff / staff123")
        print("\n🌐 Open: http://127.0.0.1:5000")
    
    app.run(debug=True)