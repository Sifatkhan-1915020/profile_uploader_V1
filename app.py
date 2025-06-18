from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import os
from werkzeug.utils import secure_filename
from bson.objectid import ObjectId

# Initialize Flask app
app = Flask(__name__)

# MongoDB Configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/medicalImages"
app.config['SECRET_KEY'] = 'your-secret-key'  # Used for sessions
mongo = PyMongo(app)

# Flask-Login Configuration
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# File Upload Configuration
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['PROFILE_PIC_FOLDER'] = 'static/profile_pics'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}


# Helper function to check file extension
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# User Class for Flask-Login
class User(UserMixin):
    def __init__(self, username, password, _id, profile_pic=None):
        self.id = _id
        self.username = username
        self.password = password
        self.profile_pic = profile_pic


# Load User by ID for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data['username'], user_data['password'], str(user_data['_id']), user_data.get('profile_pic'))
    return None


# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        profile_pic = None

        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['PROFILE_PIC_FOLDER'], filename)
                file.save(filepath)
                profile_pic = filename  # Save only the filename (not the full path)

        existing_user = mongo.db.users.find_one({'username': username})

        if existing_user:
            flash("Username already exists!", "error")
        else:
            # Insert user with profile picture (only saving the filename in DB)
            mongo.db.users.insert_one({'username': username, 'password': password, 'profile_pic': profile_pic})
            flash("Signup successful!", "success")
            return redirect(url_for('login'))

    return render_template('signup.html')


# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = mongo.db.users.find_one({'username': username, 'password': password})

        if user_data:
            user = User(user_data['username'], user_data['password'], str(user_data['_id']),
                        user_data.get('profile_pic'))
            login_user(user)
            return redirect(url_for('profile'))

        flash("Invalid credentials", "error")

    return render_template('login.html')


# Logout route
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# Profile route
@app.route('/profile')
@login_required
def profile():
    user_images = mongo.db.images.find({'user_id': current_user.id})
    all_users = mongo.db.users.find()  # To display other user profiles
    return render_template('profile.html', images=user_images, users=all_users)


# Home route
@app.route('/')
def index():
    return redirect(url_for('login'))


# Image upload route
@app.route('/upload', methods=['POST'])
@login_required
def upload_image():
    if 'file' not in request.files:
        return redirect('/')
    file = request.files['file']

    if file.filename == '':
        return redirect('/')

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Save file information to MongoDB with the user's ID
        mongo.db.images.insert_one(
            {'filename': filename, 'filepath': filepath, 'user_id': current_user.id, 'comments': []})

        return redirect('/profile')

    return 'File type not allowed'


# Delete image route
@app.route('/delete/<image_id>')
@login_required
def delete_image(image_id):
    image = mongo.db.images.find_one({'_id': ObjectId(image_id)})

    # Check if the image belongs to the current user
    if image and str(image['user_id']) == current_user.id:
        mongo.db.images.delete_one({'_id': ObjectId(image_id)})
        flash("Image deleted successfully", "success")
    else:
        flash("You are not authorized to delete this image", "error")

    return redirect('/profile')


# View other profile route
@app.route('/profile/<user_id>')
@login_required
def view_profile(user_id):
    user_images = mongo.db.images.find({'user_id': user_id})
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return render_template('profile_view.html', images=user_images, user=user_data)


# Comment on image route
@app.route('/comment/<image_id>', methods=['POST'])
@login_required
def comment_on_image(image_id):
    comment = request.form['comment']
    image = mongo.db.images.find_one({'_id': ObjectId(image_id)})

    if image:
        mongo.db.images.update_one({'_id': ObjectId(image_id)},
                                   {'$push': {'comments': {'user_id': current_user.id, 'comment': comment}}})

    # Redirect to the image's original profile page (whether own or other user's)
    return redirect(request.referrer)
# Route to view comments for a specific image
@app.route('/comments/<image_id>')
@login_required
def view_comments(image_id):
    # Find the image from MongoDB using the image_id
    image = mongo.db.images.find_one({'_id': ObjectId(image_id)})

    if not image:
        flash("Image not found", "error")
        return redirect(url_for('profile'))  # Redirect to profile if image not found

    # Render a template with the image and its comments
    return render_template('view_comments.html', image=image)


if __name__ == '__main__':
    app.run(debug=True)
