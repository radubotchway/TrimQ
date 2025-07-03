# TrimQ - Professional Queue Management System

A comprehensive multi-branch queue management system designed specifically for Ghanaian barber shops and salons, featuring real-time revenue tracking, customer management, and professional ticketing.

![TrimQ System](https://img.shields.io/badge/TrimQ-Professional-success?style=for-the-badge&logo=scissors) 
![Ghana Ready](https://img.shields.io/badge/Ghana-Ready-green?style=for-the-badge) 
![Multi Branch](https://img.shields.io/badge/Multi-Branch-blue?style=for-the-badge)

## 🌟 Key Features

### 🏢 Multi-Branch Franchise Management
- **Centralized Control**: Master admin dashboard for franchise owners
- **Branch Independence**: Individual admin controls for each location
- **Real-Time Monitoring**: Live statistics across all branches
- **Scalable Architecture**: Easy addition of new branches

### 📱 Digital Queue System
- **Paperless Operations**: Replace traditional paper queues
- **Customer Registration**: Name, phone, service selection with notes
- **Barber Assignment**: Real-time staff allocation and tracking
- **Wait Time Estimation**: Automatic calculations based on service duration
- **Ticket Generation**: Professional printable tickets with QR codes

### 💰 Financial Management
- **Ghana Cedis Integration**: Built-in GH₵ currency support
- **Real-Time Revenue**: Live tracking as services complete
- **Service Pricing**: Customizable pricing for different service types
- **Daily Reports**: Comprehensive revenue analytics
- **Branch Comparison**: Performance metrics across locations

### 👥 Customer Relationship Management
- **Customer Database**: Comprehensive customer profiles with photos
- **Visit History**: Track customer loyalty and preferences
- **Phone Integration**: Quick customer lookup and queue addition
- **Notes System**: Special requirements and customer preferences
- **Analytics**: Customer frequency and spending patterns

### 🎯 Public Display System
- **Customer-Facing Screen**: Clean, professional waiting area display
- **Auto-Refresh**: Updates every 30 seconds without manual intervention
- **Queue Status**: Real-time "Now Serving" and "Up Next" displays
- **Ghana Branding**: Culturally appropriate design elements

### 🔐 Role-Based Access Control
- **Master Admin**: Full system access across all branches
- **Branch Admin**: Complete control over assigned branch
- **Staff Access**: Basic queue management capabilities
- **Secure Authentication**: Password-protected with role verification
- **Email Integration**: Password reset functionality

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.8 or higher
- Modern web browser (Chrome, Firefox, Safari, Edge)
- Network access for multi-device usage

### Installation

1. **Download and Setup**
   ```bash
   # Clone or download the project files
   # Ensure you have all files including app.py and templates folder
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize and Run**
   ```bash
   python app.py
   ```

4. **Access the System**
   - Open browser to `http://127.0.0.1:5000`
   - Database and sample data created automatically
   - Ready to use immediately!

## 👥 Default User Accounts

| Role | Username | Password | Access Level | Description |
|------|----------|----------|--------------|-------------|
| **Master Admin** | `master_admin` | `master123` | All branches + system settings | Franchise owner access |
| **Main Branch** | `main_admin` | `main123` | Main Branch only | Oxford Street, Osu |
| **Downtown** | `downtown_admin` | `downtown123` | Downtown Branch only | Kwame Nkrumah Ave |
| **East Legon** | `uptown_admin` | `uptown123` | East Legon Branch only | Liberation Road |

⚠️ **SECURITY**: Change these passwords immediately in production!

## 🏪 Pre-Configured Branches

### 1. Main Branch (Osu)
- **Address**: 123 Oxford Street, Osu
- **Phone**: 0302-123-456
- **Code**: `main`
- **Features**: Full service flagship location

### 2. Downtown Branch (Adabraka)
- **Address**: 45 Kwame Nkrumah Ave, Adabraka
- **Phone**: 0302-789-012
- **Code**: `downtown`
- **Features**: High-traffic commercial area

### 3. East Legon Branch (Residential)
- **Address**: 78 Liberation Road, East Legon
- **Phone**: 0302-345-678
- **Code**: `uptown`
- **Features**: Premium residential location

## 💼 Default Services Catalog

| Service | Duration | Price (GH₵) | Description |
|---------|----------|-------------|-------------|
| **Classic Cut** | 30 min | ₵50 | Standard haircut service |
| **Beard Styling** | 20 min | ₵35 | Professional beard grooming |
| **Hot Towel Shave** | 25 min | ₵40 | Traditional shaving experience |
| **Full Service** | 60 min | ₵80 | Complete grooming package |
| **Quick Trim** | 15 min | ₵25 | Express touch-up service |

*All prices can be customized per branch requirements*

## 📱 System Workflow

### For Branch Staff:
1. **Login** → Use branch-specific credentials
2. **Add Customers** → Name, phone, service selection
3. **Generate Tickets** → Optional printable queue tickets
4. **Assign to Barbers** → Real-time staff allocation
5. **Complete Services** → Automatic revenue tracking
6. **Monitor Performance** → Live dashboard analytics

### For Customers:
1. **Registration** → Staff-assisted queue entry
2. **Receive Ticket** → Printed ticket with queue position
3. **Monitor Status** → Public display screen updates
4. **Service Assignment** → Called when barber available
5. **Service Completion** → Payment and checkout

### For Master Admin:
1. **System Overview** → Franchise-wide dashboard
2. **Branch Management** → Add/edit locations and settings
3. **Staff Management** → User accounts and permissions
4. **Revenue Analysis** → Cross-branch performance comparison
5. **Customer Insights** → Franchise-wide customer analytics

## 🎨 Design Philosophy

### Ghana-Inspired Aesthetics
- **National Colors**: Green, gold, and red throughout
- **Cultural Elements**: Ghana flag integration and local sensibilities
- **Professional Feel**: Clean, modern interface suitable for business

### User Experience Focus
- **Intuitive Navigation**: Minimal learning curve for staff
- **Mobile Responsive**: Works on phones, tablets, and desktops
- **Accessibility**: Clear typography and high contrast design
- **Speed Optimized**: Fast loading for busy environments

## 🔧 Advanced Configuration

### Adding New Branches
1. Master Admin → Settings → Branch Management
2. Enter branch code, name, address, phone
3. Create branch admin account
4. Add barbers to the new location
5. Customize services and pricing if needed

### Customizing Services
1. Settings → Services Management
2. Add services with duration and pricing
3. Edit existing services (Master Admin only)
4. Services are shared across all branches

### Managing Staff
1. Settings → User Management
2. Add users with appropriate roles and branch assignments
3. Set up email addresses for password reset functionality
4. Manage user permissions and access levels

### Revenue Configuration
- Real-time calculation based on completed services
- Automatic currency formatting in Ghana Cedis
- Daily, weekly, and monthly reporting capabilities
- Export functionality for external accounting systems

## 📊 Reporting and Analytics

### Real-Time Revenue Tracking
- **Live Updates**: Revenue calculated as services complete
- **Branch Comparison**: Side-by-side performance metrics
- **Service Breakdown**: Most popular and profitable services
- **Hourly Trends**: Peak business hours identification

### Customer Analytics
- **Visit Frequency**: Customer loyalty tracking
- **Service Preferences**: Most requested services per customer
- **Geographic Analysis**: Customer distribution by area
- **Growth Metrics**: New vs. returning customer ratios

### Operational Insights
- **Queue Efficiency**: Average wait times and service duration
- **Barber Performance**: Individual staff productivity
- **Peak Hours**: Busiest times for staffing optimization
- **Revenue Trends**: Daily, weekly, and monthly patterns

## 🛡️ Security Features

### Data Protection
- **Password Hashing**: Secure password storage using Werkzeug
- **Session Management**: Flask-Login for secure user sessions
- **Role Verification**: Strict access control based on permissions
- **CSRF Protection**: Form security against cross-site attacks

### Input Validation
- **Server-Side Validation**: All user inputs validated
- **Phone Number Formatting**: Ghana-specific phone validation
- **SQL Injection Prevention**: Parameterized database queries
- **File Upload Security**: Image validation and size limits

## 🌐 Technical Architecture

### Backend Stack
- **Framework**: Flask (Python)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Authentication**: Flask-Login with role-based access
- **Forms**: Flask-WTF + WTForms with validation
- **File Handling**: Werkzeug with PIL for image processing

### Frontend Technologies
- **UI Framework**: Bootstrap 5 with custom CSS
- **Icons**: Bootstrap Icons
- **Typography**: Google Fonts (Poppins)
- **Interactivity**: Vanilla JavaScript with AJAX
- **Responsive Design**: Mobile-first approach

### Database Schema
- **Users**: Authentication and role management
- **Branches**: Location information and settings
- **Services**: Service catalog with pricing
- **Customers**: Customer profiles and queue status
- **Visit History**: Complete audit trail of services
- **Barbers**: Staff assignments by branch

## 🚀 Production Deployment

### Security Checklist
- [ ] Update `SECRET_KEY` in application configuration
- [ ] Change all default passwords for user accounts
- [ ] Configure production database (PostgreSQL recommended)
- [ ] Enable HTTPS with SSL certificates
- [ ] Set up proper logging and monitoring
- [ ] Configure automated backup strategy
- [ ] Implement proper error handling

### Environment Configuration
```bash
# Production environment variables
export SECRET_KEY="your-production-secret-key-here"
export DATABASE_URL="postgresql://user:password@localhost/trimq_production"
export FLASK_ENV="production"
export MAIL_SERVER="your-smtp-server.com"
export MAIL_USERNAME="your-email@domain.com"
export MAIL_PASSWORD="your-email-password"
```

### Performance Optimization
- Use production WSGI server (Gunicorn recommended)
- Configure reverse proxy (Nginx) for static file serving
- Enable database connection pooling
- Implement Redis for session storage
- Set up CDN for static assets

## 📱 Mobile Integration

### Responsive Design
- **Touch-Friendly**: Large buttons and touch targets
- **Readable Text**: Optimized font sizes for mobile screens
- **Fast Loading**: Optimized images and minimal JavaScript
- **Offline Capability**: Service worker for basic offline functionality

### Public Display Optimization
- **Large Screen Support**: Optimized for TV displays in waiting areas
- **Auto-Refresh**: Automatic updates without user intervention
- **High Contrast**: Easy reading from distance
- **Landscape Layout**: Optimized for wide screen displays

## 🔧 Troubleshooting

### Common Issues
1. **Database Errors**: Check file permissions and restart application
2. **Login Problems**: Verify credentials and check user status
3. **Image Upload Issues**: Ensure upload folder permissions are correct
4. **Email Not Working**: Configure SMTP settings in environment variables

### Support Resources
- Check application logs for detailed error information
- Review Flask documentation for framework-specific issues
- Consult Bootstrap documentation for UI customization
- Contact system administrator for user account issues

## 📄 License and Usage

This TrimQ system is designed specifically for Ghanaian small businesses and can be freely adapted for commercial use. The system includes:

- Complete source code with documentation
- Sample data for immediate testing
- Customizable branding and styling
- Multi-language support capability (English + local languages)

## 🤝 Contributing

We welcome contributions from the Ghanaian tech community:

- **Bug Reports**: Submit issues with detailed descriptions
- **Feature Requests**: Suggest improvements for local business needs
- **Code Contributions**: Submit pull requests with proper testing
- **Documentation**: Help improve setup and usage guides
- **Translations**: Add support for local Ghanaian languages

## 📞 Support and Contact

For technical support, customization requests, or business inquiries:

- **Documentation**: Review included code comments and documentation
- **Community**: Connect with other users in Ghana's tech community
- **Customization**: Modify templates and styling for your brand
- **Training**: Staff training materials included in documentation

---

**Built with ❤️ for Ghanaian entrepreneurs**

*TrimQ - Transforming traditional barbershops into modern, efficient businesses while preserving the community spirit that makes Ghanaian barber shops special.*

---

## 🎯 Quick Reference

### Keyboard Shortcuts
- **Alt + T**: Generate ticket for first waiting customer
- **Alt + C**: Complete first in-progress service  
- **Alt + R**: Refresh revenue data
- **Alt + N**: Add new customer
- **Ctrl + R**: Manual refresh (revenue reports)

### API Endpoints
- `/api/revenue/<branch_code>`: Real-time branch revenue
- `/api/revenue/all`: Franchise-wide revenue (Master Admin)
- `/api/customers`: Customer management endpoints
- `/api/remove_customer/<id>`: Remove customer from queue

### Default Ports and URLs
- **Application**: http://localhost:5000
- **Public Display**: /display/<branch_code>
- **Admin Panel**: /settings
- **Revenue Reports**: /revenue-report