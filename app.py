from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import os
import json
import time
import threading
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from werkzeug.utils import secure_filename
import sys

# Import randomize module from local directory
from randomize import randomize_email_template

app = Flask(__name__)
app.secret_key = "sendapp_secret_key"  # Change this to a random secret key in production

# Configuration
UPLOAD_FOLDER = 'uploads'
ACCOUNTS_FOLDER = os.path.join(UPLOAD_FOLDER, 'accounts')
DATA_FOLDER = os.path.join(UPLOAD_FOLDER, 'data')
ALLOWED_EXTENSIONS = {'txt', 'csv', 'json'}

# Create necessary directories
os.makedirs(ACCOUNTS_FOLDER, exist_ok=True)
os.makedirs(DATA_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Global variables for sender state
sender_thread = None
is_sending = False
is_paused = False
current_progress = 0
total_emails = 0
current_account = ""
current_data_file = ""
sending_speed = 5  # Default sending speed in seconds
start_line = 0
email_count = 0  # Number of emails to send, 0 means all

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Load accounts from file
def load_accounts(filename):
    accounts = []
    filepath = os.path.join(ACCOUNTS_FOLDER, filename)
    
    if not os.path.exists(filepath):
        return []
        
    with open(filepath, 'r') as f:
        for line in f:
            if ':' in line:
                email, password = line.strip().split(':', 1)
                accounts.append({"email": email, "password": password})
    return accounts

# Load data from file
def load_data(filename):
    data = []
    filepath = os.path.join(DATA_FOLDER, filename)
    
    if not os.path.exists(filepath):
        return []
        
    with open(filepath, 'r') as f:
        for line in f:
            data.append(line.strip())
    return data

# Load email template from file
def load_email_template():
    template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'email_template.txt')
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        return template
    except Exception as e:
        print(f"Error loading email template: {e}")
        return ""

# Send email function
def send_email(from_email, from_password, to_email, subject, body, from_name=None):
    try:
        # Randomize the email template before processing
        randomized_template, _ = randomize_email_template(body)
        
        # Extract headers and body
        headers_match = re.search(r'(.*?)\r?\n\r?\n(.*)', randomized_template, re.DOTALL)
        if headers_match:
            headers_str = headers_match.group(1)
            body = headers_match.group(2)
        else:
            headers_str = ""
            body = randomized_template

        # Create a dictionary of existing headers (case-insensitive keys)
        header_dict = {}
        if headers_str:
            for line in headers_str.splitlines(): # Use splitlines for robustness
                if ':' in line:
                    key, value = line.split(':', 1)
                    header_dict[key.strip().lower()] = value.strip()

        # Set/Overwrite essential headers
        if from_name:
            header_dict['from'] = f"{from_name} <{from_email}>"
        else:
            header_dict['from'] = from_email
        header_dict['to'] = to_email
        header_dict['subject'] = subject

        # Rebuild the headers string
        final_headers = []
        for key, value in header_dict.items():
            # Ensure standard capitalization (e.g., From, To, Subject)
            header_name = '-'.join(part.capitalize() for part in key.split('-'))
            final_headers.append(f"{header_name}: {value}")

        # Combine headers and body
        email_content = '\r\n'.join(final_headers) + '\r\n\r\n' + body
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, from_password)
        server.sendmail(from_email, to_email, email_content.encode('utf-8'))
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Sender function to run in a separate thread
def sender_task(accounts, data, subjects, from_names, body, speed, start_from, max_count, test_after=0, test_email=''):
    global is_sending, is_paused, current_progress, total_emails, current_account
    
    if not accounts or not data:
        is_sending = False
        return
    
    account_index = 0
    rotation_index = 0  # Index for rotating through subjects and from_names
    total_data = len(data)
    emails_since_test = 0  # Counter for tracking emails sent since last test
    
    if max_count > 0:
        total_emails = min(max_count, total_data - start_from)
    else:
        total_emails = total_data - start_from
    
    current_progress = 0
    
    for i in range(start_from, start_from + total_emails):
        if i >= total_data:
            break
            
        while is_paused and is_sending:
            time.sleep(1)
            
        if not is_sending:
            break
            
        to_email = data[i]
        account = accounts[account_index]
        current_account = account["email"]
        
        # Get current subject and from_name based on rotation index
        current_subject = subjects[rotation_index % len(subjects)]
        current_from_name = from_names[rotation_index % len(from_names)]
        
        success = send_email(
            account["email"], 
            account["password"], 
            to_email, 
            current_subject, 
            body,
            current_from_name
        )
        
        if success:
            current_progress += 1
            emails_since_test += 1  # Increment test counter
            
            # Check if we need to send a test email
            if test_after > 0 and test_email and emails_since_test >= test_after:
                print(f"Sending test email to {test_email} after {emails_since_test} regular emails")
                test_subject = f"Test Email - After {emails_since_test} Regular Emails"
                
                # Use the next account for the test email
                test_account_index = (account_index + 1) % len(accounts)
                test_account = accounts[test_account_index]
                
                test_success = send_email(
                    test_account["email"],
                    test_account["password"],
                    test_email,
                    test_subject,
                    body,
                    current_from_name
                )
                
                if test_success:
                    print(f"Test email sent successfully to {test_email}")
                    emails_since_test = 0  # Reset counter
                else:
                    print(f"Failed to send test email to {test_email}")
        
        # Rotate accounts
        account_index = (account_index + 1) % len(accounts)
        
        # Rotate subjects and from_names
        rotation_index += 1
        
        # Sleep according to speed setting (seconds between emails)
        time.sleep(speed)
    
    is_sending = False

@app.route('/')
def index():
    # Get list of available account and data files
    account_files = [f for f in os.listdir(ACCOUNTS_FOLDER) if allowed_file(f)]
    data_files = [f for f in os.listdir(DATA_FOLDER) if allowed_file(f)]
    
    # Load email template
    email_template = load_email_template()
    
    return render_template('index.html', 
                          account_files=account_files,
                          data_files=data_files,
                          is_sending=is_sending,
                          is_paused=is_paused,
                          email_template=email_template)

@app.route('/upload', methods=['POST'])
def upload_file():
    file_type = request.form.get('file_type')
    
    if 'file' not in request.files:
        return redirect(request.url)
        
    file = request.files['file']
    
    if file.filename == '':
        return redirect(request.url)
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        
        if file_type == 'accounts':
            file.save(os.path.join(ACCOUNTS_FOLDER, filename))
        elif file_type == 'data':
            file.save(os.path.join(DATA_FOLDER, filename))
            
    return redirect(url_for('index'))

@app.route('/start', methods=['POST'])
def start_sending():
    global sender_thread, is_sending, is_paused, current_data_file, current_account, sending_speed, start_line, email_count
    
    if is_sending:
        return jsonify({"status": "error", "message": "Already sending"})
    
    account_file = request.form.get('account_file')
    data_file = request.form.get('data_file')
    subjects_text = request.form.get('subjects')
    from_names_text = request.form.get('from_names')
    body = request.form.get('body')
    # Convert emails per hour to seconds between emails
    sending_speed = 3600 / float(request.form.get('speed', 720))
    start_line = int(request.form.get('start_line', 0))
    email_count = int(request.form.get('count', 0))
    test_after = int(request.form.get('test_after', 0))
    test_email = request.form.get('testEmail', '')
    
    # Parse subjects and from_names into lists
    subjects = [s.strip() for s in subjects_text.splitlines() if s.strip()]
    from_names = [n.strip() for n in from_names_text.splitlines() if n.strip()]
    
    # Ensure we have at least one subject and from_name
    if not subjects:
        return jsonify({"status": "error", "message": "At least one subject is required"})
    
    if not from_names:
        return jsonify({"status": "error", "message": "At least one sender name is required"})
    
    accounts = load_accounts(account_file)
    data = load_data(data_file)
    
    if not accounts:
        return jsonify({"status": "error", "message": "No accounts found"})
        
    if not data:
        return jsonify({"status": "error", "message": "No data found"})
    
    current_data_file = data_file
    is_sending = True
    is_paused = False
    
    sender_thread = threading.Thread(
        target=sender_task,
        args=(accounts, data, subjects, from_names, body, sending_speed, start_line, email_count, test_after, test_email)
    )
    sender_thread.daemon = True
    sender_thread.start()
    
    return jsonify({"status": "success", "message": "Sending started"})

@app.route('/pause', methods=['POST'])
def pause_sending():
    global is_paused
    
    if not is_sending:
        return jsonify({"status": "error", "message": "Not sending"})
    
    is_paused = not is_paused
    status = "paused" if is_paused else "resumed"
    
    return jsonify({"status": "success", "message": f"Sending {status}"})

@app.route('/stop', methods=['POST'])
def stop_sending():
    global is_sending
    
    if not is_sending:
        return jsonify({"status": "error", "message": "Not sending"})
    
    is_sending = False
    
    return jsonify({"status": "success", "message": "Sending stopped"})

@app.route('/status')
def get_status():
    return jsonify({
        "is_sending": is_sending,
        "is_paused": is_paused,
        "progress": current_progress,
        "total": total_emails,
        "current_account": current_account,
        "current_data_file": current_data_file
    })

@app.route('/accounts')
def view_accounts():
    account_file = request.args.get('file')
    accounts = []
    
    if account_file:
        accounts = load_accounts(account_file)
    
    account_files = [f for f in os.listdir(ACCOUNTS_FOLDER) if allowed_file(f)]
    
    return render_template('accounts.html', 
                          accounts=accounts,
                          account_files=account_files,
                          current_file=account_file)

@app.route('/data')
def view_data():
    data_file = request.args.get('file')
    data = []
    
    if data_file:
        data = load_data(data_file)
    
    data_files = [f for f in os.listdir(DATA_FOLDER) if allowed_file(f)]
    
    return render_template('data.html', 
                          data=data,
                          data_files=data_files,
                          current_file=data_file)
@app.route('/test-email', methods=['POST'])
def test_email():
    account_file = request.form.get('account_file')
    subjects_text = request.form.get('subjects')
    from_names_text = request.form.get('from_names')
    body = request.form.get('body')
    test_email = request.form.get('test_email')
    test_count = int(request.form.get('test_count', '1'))
    
    if not account_file:
        return jsonify({"status": "error", "message": "Please select an account file"})
    
    if not subjects_text or not from_names_text:
        return jsonify({"status": "error", "message": "Subjects and sender names are required"})
    
    if not body:
        return jsonify({"status": "error", "message": "Email body is required"})
    
    if not test_email:
        return jsonify({"status": "error", "message": "Test email address is required"})
    
    # Parse subjects and from_names
    subjects = [s.strip() for s in subjects_text.splitlines() if s.strip()]
    from_names = [n.strip() for n in from_names_text.splitlines() if n.strip()]
    
    if not subjects or not from_names:
        return jsonify({"status": "error", "message": "At least one subject and sender name are required"})
    
    accounts = load_accounts(account_file)
    
    if not accounts:
        return jsonify({"status": "error", "message": "No accounts found in the selected file"})
    
    # Limit test_count to the number of available combinations
    max_combinations = min(len(subjects), len(from_names))
    if test_count > max_combinations:
        test_count = max_combinations
    
    # Send test emails
    success_count = 0
    account_index = 0  # Initialize account index for rotation
    
    for i in range(test_count):
        # Rotate through accounts for each test email
        account = accounts[account_index]
        account_index = (account_index + 1) % len(accounts)  # Rotate to next account
        
        idx = i % max_combinations
        current_subject = subjects[idx % len(subjects)]
        current_from_name = from_names[idx % len(from_names)]
        
        success = send_email(
            account["email"],
            account["password"],
            test_email,
            f"TEST {idx+1}: {current_subject}",
            body,
            current_from_name
        )
        
        if success:
            success_count += 1
    
    if success_count == test_count:
        return jsonify({"status": "success", "message": f"{success_count} test email(s) sent successfully with randomized tags"})
    elif success_count > 0:
        return jsonify({"status": "success", "message": f"{success_count} of {test_count} test emails sent successfully"})
    else:
        return jsonify({"status": "error", "message": "Failed to send test emails. Check account credentials and settings."})
@app.route('/save-template', methods=['POST'])
def save_template():
    body = request.form.get('body')
    
    if not body:
        return jsonify({"status": "error", "message": "Email template body is required"})
    
    try:
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'email_template.txt')
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(body)
        return jsonify({"status": "success", "message": "Email template saved successfully"})
    except Exception as e:
        print(f"Error saving email template: {e}")
        return jsonify({"status": "error", "message": f"Failed to save email template: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)