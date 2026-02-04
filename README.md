SaySo - A WEB-BASED ANONYMOUS CUSTOMER FEEDBACK PLATFORM​
SaySo is Flask-based, developed to allow users to create, share, and manage questionnaires, collect responses, and view responses through a simple web interface.

Created for academic purposes by Hadia Javed (19929589)

My webapp is deployed online and can be accessed here:
https://hadiajaved.pythonanywhere.com

The application requires user authentication to access the core functionalities to test the system you can:
- Create a new account using Sign up page click the button under the login. e.g. (username = test123, password test123)
- Log in with the newly created username and password.
- You are redirected to the homepage where you can create a questionnaire.
- Your created questionnaires will show up on your homepage dashboard where you can click the three dots to share, edit, delete or view responses of customers.
- Through the profile icon you can update your username or delete your account.
- You can also get help from the help button.
- You can log out at any time by pressing log out.

Technologies used:
Python(Flask)
Flask - SQLAlchemy
SQLite
HTML, CSS, JavaScript
qrcode - Pillow

How to run locally:
1. Download the zipped code and extract
2. Create and activate virtual environment
   macOS = source venv/bin/activate
3. Install dependencies
   pip install -r requirements.txt
4. Run the application
   macOS = python3 app.py

