# File: app.py - Clean TrimQ Application
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, TextAreaField, PasswordField, IntegerField, FloatField
from wtforms.validators import DataRequired, Length
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

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

# ============================================================================
# MODELS
# ============================================================================

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    branch = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='branch_admin')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_master_admin(self):
        return self.role == 'master_admin'
    
    def is_branch_admin(self):
        return self.role == 'branch_admin'

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
    duration = db.Column(db.Integer)
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
    status = db.Column(db.String(20), default='waiting')
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
    return db.session.get(User, int(user_id))

# ============================================================================
# FORMS
# ============================================================================

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Sign In')

class CustomerForm(FlaskForm):
    name = StringField('Customer Name', validators=[DataRequired(), Length(max=100)])
    phone = StringField('Phone Number', validators=[DataRequired(), Length(max=20)])
    service_id = SelectField('Select Service', coerce=int, validators=[DataRequired()])
    notes = TextAreaField('Special Notes (Optional)')
    submit = SubmitField('Add to Queue')

    def __init__(self, *args, **kwargs):
        super(CustomerForm, self).__init__(*args, **kwargs)
        services = Service.query.filter_by(is_active=True).order_by('name').all()
        self.service_id.choices = [(s.id, f"{s.name} ({s.duration} min • GH₵{s.price:.0f})") for s in services]

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_branches_dict():
    """Get active branches as a dictionary"""
    branches = Branch.query.filter_by(is_active=True).all()
    return {
        branch.code: {
            'name': branch.name,
            'address': branch.address,
            'phone': branch.phone
        }
        for branch in branches
    }

def get_wait_time(customer):
    """Calculate estimated wait time"""
    if customer.status != 'waiting':
        return None
    
    earlier_customers = Customer.query.filter(
        Customer.branch == customer.branch,
        Customer.status == 'waiting',
        Customer.created_at < customer.created_at
    ).order_by(Customer.created_at).all()
    
    total_wait = sum(Service.query.get(c.service_id).duration or 0 for c in earlier_customers)
    
    if total_wait == 0:
        return "Up Next!"
    elif total_wait <= 15:
        return f"~{total_wait} min"
    else:
        return f"~{total_wait} min"

def get_branch_stats(branch_code):
    """Get statistics for a branch"""
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

@app.context_processor
def inject_helpers():
    return {
        'now': datetime.now(),
        'get_wait_time': get_wait_time,
        'BRANCHES': get_branches_dict()
    }

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    if not current_user.is_authenticated:
        return render_template('welcome.html')
    
    if current_user.is_master_admin():
        # Master admin dashboard
        branches_dict = get_branches_dict()
        branch_stats = {code: get_branch_stats(code) for code in branches_dict.keys()}
        franchise_stats = {
            'total_waiting': sum(stats['waiting'] for stats in branch_stats.values()),
            'total_in_progress': sum(stats['in_progress'] for stats in branch_stats.values()),
            'total_completed_today': sum(stats['completed_today'] for stats in branch_stats.values()),
            'total_barbers': sum(stats['active_barbers'] for stats in branch_stats.values())
        }
        return render_template('master_dashboard.html',
                             franchise_stats=franchise_stats,
                             branch_stats=branch_stats)
    else:
        # Branch admin dashboard
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
            flash(f'Welcome back!', 'success')
            return redirect(url_for('index'))
        flash('Invalid credentials.', 'error')
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
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    branch_stats = get_branch_stats(branch_code)
    branches_dict = get_branches_dict()
    branch_info = branches_dict.get(branch_code, {})
    
    return render_template('branch_dashboard.html',
                         branch_code=branch_code,
                         branch_info=branch_info,
                         **branch_stats)

@app.route('/add/<branch_code>', methods=['GET', 'POST'])
@login_required
def add_customer(branch_code=None):
    if not branch_code:
        branch_code = current_user.branch
    
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
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
        flash(f'{customer.name} added to queue!', 'success')
        return redirect(url_for('queue_manage', branch_code=branch_code))
    
    branches_dict = get_branches_dict()
    return render_template('add_customer.html', 
                         form=form, 
                         branch_code=branch_code, 
                         branch_info=branches_dict.get(branch_code, {}))

@app.route('/queue/<branch_code>')
@login_required
def queue_manage(branch_code):
    if not current_user.is_master_admin() and current_user.branch != branch_code:
        flash('Access denied.', 'error')
        return redirect(url_for('index'))
    
    waiting = Customer.query.filter_by(branch=branch_code, status='waiting').order_by(Customer.created_at).all()
    in_progress = Customer.query.filter_by(branch=branch_code, status='assigned').order_by(Customer.assigned_at).all()
    barbers = Barber.query.filter_by(branch=branch_code, is_active=True).order_by(Barber.name).all()
    
    branches_dict = get_branches_dict()
    return render_template('queue.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         barbers=barbers,
                         branch_code=branch_code,
                         branch_info=branches_dict.get(branch_code, {}))

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
        flash(f'{customer.name} assigned to {barber.name}', 'success')
    
    return redirect(url_for('queue_manage', branch_code=customer.branch))

@app.route('/complete/<int:customer_id>')
@login_required
def complete_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.status = 'completed'
    customer.completed_at = datetime.utcnow()
    db.session.commit()
    flash(f'{customer.name} service completed!', 'success')
    return redirect(url_for('queue_manage', branch_code=customer.branch))

@app.route('/display/<branch_code>')
def public_display(branch_code):
    waiting = Customer.query.filter_by(branch=branch_code, status='waiting').order_by(Customer.created_at).all()
    in_progress = Customer.query.filter_by(branch=branch_code, status='assigned').order_by(Customer.assigned_at).all()
    
    branches_dict = get_branches_dict()
    return render_template('display.html', 
                         waiting=waiting,
                         in_progress=in_progress,
                         branch_code=branch_code,
                         branch_info=branches_dict.get(branch_code, {}))

@app.route('/settings')
@login_required
def settings():
    services = Service.query.order_by(Service.name).all()
    
    if current_user.is_master_admin():
        barbers = Barber.query.order_by(Barber.branch, Barber.name).all()
        branches = Branch.query.order_by(Branch.name).all()
    else:
        barbers = Barber.query.filter_by(branch=current_user.branch).order_by(Barber.name).all()
        branches = []
    
    return render_template('settings.html', services=services, barbers=barbers, branches=branches)

@app.route('/add_service', methods=['POST'])
@login_required
def add_service():
    name = request.form.get('name')
    duration = request.form.get('duration')
    price = request.form.get('price')
    
    if name and duration and price:
        service = Service(name=name, duration=int(duration), price=float(price))
        db.session.add(service)
        db.session.commit()
        flash(f'Service "{name}" added!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/add_barber', methods=['POST'])
@login_required
def add_barber():
    name = request.form.get('name')
    branch = request.form.get('branch')
    
    if name and branch:
        barber = Barber(name=name, branch=branch)
        db.session.add(barber)
        db.session.commit()
        flash(f'Barber "{name}" added!', 'success')
    
    return redirect(url_for('settings'))

@app.route('/add_branch', methods=['POST'])
@login_required
def add_branch():
    if not current_user.is_master_admin():
        flash('Access denied.', 'error')
        return redirect(url_for('settings'))
    
    code = request.form.get('code', '').lower().strip()
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if code and name and address:
        if not Branch.query.filter_by(code=code).first():
            branch = Branch(code=code, name=name, address=address, phone=phone)
            db.session.add(branch)
            db.session.commit()
            flash(f'Branch "{name}" added!', 'success')
        else:
            flash('Branch code already exists!', 'error')
    
    return redirect(url_for('settings'))

@app.route('/toggle_service/<int:service_id>')
@login_required
def toggle_service(service_id):
    service = Service.query.get_or_404(service_id)
    service.is_active = not service.is_active
    db.session.commit()
    return redirect(url_for('settings'))

@app.route('/toggle_barber/<int:barber_id>')
@login_required
def toggle_barber(barber_id):
    barber = Barber.query.get_or_404(barber_id)
    barber.is_active = not barber.is_active
    db.session.commit()
    return redirect(url_for('settings'))

# ============================================================================
# INITIALIZATION
# ============================================================================

def create_sample_data():
    """Create sample data"""
    # Create branches
    branches_data = [
        {'code': 'main', 'name': 'Main Branch', 'address': '123 Oxford Street, Osu', 'phone': '0302-123-456'},
        {'code': 'downtown', 'name': 'Downtown Branch', 'address': '45 Kwame Nkrumah Ave, Adabraka', 'phone': '0302-789-012'},
        {'code': 'uptown', 'name': 'East Legon Branch', 'address': '78 Liberation Road, East Legon', 'phone': '0302-345-678'}
    ]
    
    for branch_data in branches_data:
        if not Branch.query.filter_by(code=branch_data['code']).first():
            branch = Branch(**branch_data)
            db.session.add(branch)
    
    # Create services
    services_data = [
        {'name': 'Classic Cut', 'duration': 30, 'price': 50},
        {'name': 'Beard Styling', 'duration': 20, 'price': 35},
        {'name': 'Hot Towel Shave', 'duration': 25, 'price': 40},
        {'name': 'Full Service', 'duration': 60, 'price': 80},
        {'name': 'Quick Trim', 'duration': 15, 'price': 25}
    ]
    
    for service_data in services_data:
        if not Service.query.filter_by(name=service_data['name']).first():
            service = Service(**service_data)
            db.session.add(service)
    
    # Create barbers
    barbers_data = [
        {'name': 'Kwame Asante', 'branch': 'main'},
        {'name': 'Kofi Mensah', 'branch': 'main'},
        {'name': 'Yaw Boateng', 'branch': 'downtown'},
        {'name': 'Samuel Osei', 'branch': 'downtown'},
        {'name': 'Isaac Adjei', 'branch': 'uptown'},
        {'name': 'Prince Agyemang', 'branch': 'uptown'}
    ]
    
    for barber_data in barbers_data:
        if not Barber.query.filter_by(name=barber_data['name'], branch=barber_data['branch']).first():
            barber = Barber(**barber_data)
            db.session.add(barber)
    
    # Create users
    users_data = [
        {'username': 'master_admin', 'password': 'master123', 'role': 'master_admin', 'branch': 'main'},
        {'username': 'main_admin', 'password': 'main123', 'role': 'branch_admin', 'branch': 'main'},
        {'username': 'downtown_admin', 'password': 'downtown123', 'role': 'branch_admin', 'branch': 'downtown'},
        {'username': 'uptown_admin', 'password': 'uptown123', 'role': 'branch_admin', 'branch': 'uptown'}
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
        print("✅ TrimQ System Ready!")
        print("\n📋 Login:")
        print("👑 Master: master_admin / master123")
        print("🏪 Branch: main_admin / main123")
        print("🏪 Branch: downtown_admin / downtown123") 
        print("🏪 Branch: uptown_admin / uptown123")
        print("\n🌐 http://127.0.0.1:5000")
    
    app.run(debug=True)