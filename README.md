# TrimQ ]
A professional multi-branch queue management system designed specifically for Ghanaian barber shops and franchises.

![TrimQ Logo](https://img.shields.io/badge/TrimQ-Franchise-success?style=for-the-badge&logo=scissors)

## 🌟 Features

### Multi-Branch Management
- **Master Admin Dashboard**: Oversee all franchise locations from one central hub
- **Branch-Specific Access**: Individual admin controls for each location
- **Real-Time Statistics**: Live queue status across all branches

### Queue Management
- **Digital Queue System**: Replace paper-based queuing with modern digital solution
- **Customer Registration**: Name, phone, service selection, and special notes
- **Barber Assignment**: Assign customers to specific barbers with real-time tracking
- **Wait Time Estimation**: Automatic calculation based on service duration and queue position

### Financial Integration
- **Ghana Cedis (GH₵) Support**: Built-in local currency formatting and calculations
- **Service Pricing**: Customizable pricing for different service types
- **Revenue Tracking**: Monitor daily completions and earnings potential

### Public Display
- **Customer-Facing Screen**: Clean, professional display for waiting areas
- **Auto-Refresh**: Updates every 30 seconds without manual intervention
- **Ghana Flag Branding**: Local cultural integration in design

### Role-Based Access Control
- **Master Admin**: Full system access across all branches
- **Branch Admin**: Complete control over assigned branch
- **Staff Access**: Basic queue management capabilities
- **Secure Authentication**: Password-protected access with role verification

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Flask and dependencies (see requirements below)

### Installation

1. **Clone or Download**
   ```bash
   # Download the project files to your local machine
   # Ensure you have app.py and all HTML template files
   ```

2. **Install Dependencies**
   ```bash
   pip install flask flask-sqlalchemy flask-login flask-wtf wtforms werkzeug
   ```

3. **Run the Application**
   ```bash
   python app.py
   ```

4. **Access the System**
   - Open your browser to `http://127.0.0.1:5000`
   - The database and sample data will be created automatically

## 👥 Default User Accounts

| Role | Username | Password | Access Level |
|------|----------|----------|--------------|
| Master Admin | `master_admin` | `master123` | All branches + system settings |
| Main Branch | `main_admin` | `main123` | Main Branch only |
| Downtown Branch | `downtown_admin` | `downtown123` | Downtown Branch only |
| East Legon Branch | `uptown_admin` | `uptown123` | East Legon Branch only |

**⚠️ IMPORTANT**: Change these default passwords in production!

## 🏢 Sample Branches

The system comes pre-configured with three sample locations:

1. **Main Branch**
   - Address: 123 Oxford Street, Osu
   - Phone: 0302-123-456
   - Code: `main`

2. **Downtown Branch**
   - Address: 45 Kwame Nkrumah Ave, Adabraka
   - Phone: 0302-789-012
   - Code: `downtown`

3. **East Legon Branch**
   - Address: 78 Liberation Road, East Legon
   - Phone: 0302-345-678
   - Code: `uptown`

## 💰 Default Services

| Service | Duration | Price (GH₵) |
|---------|----------|-------------|
| Classic Cut | 30 min | ₵50 |
| Beard Styling | 20 min | ₵35 |
| Hot Towel Shave | 25 min | ₵40 |
| Full Service | 60 min | ₵80 |
| Quick Trim | 15 min | ₵25 |

## 📱 System Workflow

### For Branch Staff:
1. **Login** with branch credentials
2. **Add Customers** to queue with service selection
3. **Assign Customers** to available barbers
4. **Mark Complete** when service is finished
5. **Monitor Queue** via management dashboard

### For Customers:
1. **Registration** at front desk with staff assistance
2. **Wait Notification** via public display screen
3. **Service Assignment** when barber becomes available
4. **Completion** and payment processing

### For Master Admin:
1. **System Overview** across all franchise locations
2. **Branch Management** - add/edit locations
3. **Service Management** - pricing and duration control
4. **Staff Management** - barber assignment and tracking
5. **Performance Monitoring** - daily statistics and trends

## 🔧 Configuration

### Adding New Branches
1. Login as Master Admin
2. Go to Settings → Branch Management
3. Fill in branch details (code, name, address, phone)
4. Create branch admin account for new location

### Customizing Services
1. Access Settings → Services
2. Add new services with pricing and duration
3. Edit existing services as needed
4. Services are shared across all branches

### Managing Staff
1. Navigate to Settings → Barbers
2. Add barbers to specific branches
3. Staff assignments are branch-specific

## 🎨 Design Features

### Ghana-Inspired Theme
- **Colors**: Green, gold, and red color scheme reflecting national identity
- **Currency**: Native Ghana Cedis (GH₵) formatting
- **Cultural Elements**: Ghana flag integration in branding

### Modern UI/UX
- **Bootstrap 5**: Responsive, mobile-friendly design
- **Bootstrap Icons**: Professional iconography throughout
- **Poppins Font**: Clean, modern typography
- **Glass Effects**: Contemporary visual styling with backdrop filters

### Responsive Design
- **Mobile Optimized**: Works seamlessly on phones and tablets
- **Desktop Focused**: Optimized for daily business use on computers
- **Public Display**: Large-screen friendly for customer viewing

## 🔒 Security Features

- **Password Hashing**: Secure password storage using Werkzeug
- **Session Management**: Flask-Login for secure user sessions
- **Role Verification**: Access control based on user permissions
- **CSRF Protection**: Flask-WTF forms with CSRF tokens
- **Input Validation**: Server-side validation for all user inputs

## 📊 Database Schema

### Core Tables:
- **Users**: Authentication and role management
- **Branches**: Location information and contact details
- **Services**: Service catalog with pricing
- **Barbers**: Staff assignments by branch
- **Customers**: Queue entries with status tracking

### Relationships:
- Users → Branches (one-to-many)
- Customers → Services (many-to-one)
- Customers → Barbers (many-to-one)
- Barbers → Branches (many-to-one)

## 🚀 Production Deployment

### Security Checklist:
- [ ] Change `SECRET_KEY` in app configuration
- [ ] Update all default passwords
- [ ] Use production database (PostgreSQL/MySQL)
- [ ] Enable HTTPS
- [ ] Set up proper logging
- [ ] Configure backup strategy

### Environment Variables:
```bash
export SECRET_KEY="your-super-secret-production-key"
export DATABASE_URL="your-production-database-url"
export FLASK_ENV="production"
```

## 🛠️ Technical Stack

- **Backend**: Flask (Python)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Frontend**: Bootstrap 5 + Custom CSS
- **Authentication**: Flask-Login
- **Forms**: Flask-WTF + WTForms
- **Icons**: Bootstrap Icons
- **Fonts**: Google Fonts (Poppins)

## 📞 Support

For technical support or customization requests:
- Review the code comments for implementation details
- Check Flask documentation for framework-specific questions
- Customize templates in the `/templates` directory
- Modify styling in the `base.html` template

## 📄 License

This project is designed for Ghanaian small businesses and can be freely adapted for commercial use.

---

**Built with ❤️ for Ghanaian entrepreneurs**

*TrimQ - Professional queue management for the modern barbershop*