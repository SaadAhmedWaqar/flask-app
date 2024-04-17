import json
import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, render_template, request
from werkzeug.middleware.proxy_fix import ProxyFix


load_dotenv()

import boto3
from botocore.exceptions import ClientError


def get_secret():

    secret_name = "flask-app-test-secret"
    region_name = "us-east-1"
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )
    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
        secret = get_secret_value_response['SecretString']
        print (secret)
        return secret
    
    except ClientError as e:
       raise e

    # secret = get_secret_value_response['SecretString']



# Load environment variables
# FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY') or 'dev'
# DB_HOST = os.getenv('DB_HOST')
# DB_NAME = os.getenv('DB_NAME')
# DB_USERNAME = os.getenv('DB_USERNAME')
# DB_PASSWORD = os.getenv('DB_PASSWORD')
    

secret = json.loads(get_secret())
print (secret)

FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY') or 'dev'
DB_HOST = secret ['endpoint']
DB_NAME = secret ['db_name']
DB_USERNAME = secret ['username']
DB_PASSWORD = secret ['password']




# If any database environment variables is not set, raise an error
if DB_HOST is None:
    raise ValueError('DB_HOST is not set')
elif DB_NAME is None:
    raise ValueError('DB_NAME is not set')
elif DB_USERNAME is None:
    raise ValueError('DB_USERNAME is not set')
elif DB_PASSWORD is None:
    raise ValueError('DB_PASSWORD is not set')

app = Flask(__name__,
            static_folder='../static',
            template_folder='../templates')
app.config['SECRET_KEY'] = FLASK_SECRET_KEY

app.wsgi_app = ProxyFix(  # type: ignore
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)


# Connect to the database
def get_db_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USERNAME,
        password=DB_PASSWORD,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    return conn

def initialize_database():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
                
    DROP TABLE IF EXISTS public.todos;

    CREATE TABLE IF NOT EXISTS public.todos
    (
        id serial,
        title text NOT NULL DEFAULT 'new todo',
        completed boolean NOT NULL DEFAULT false,
        PRIMARY KEY (id)
    );
    """)
    conn.commit()

    # Insert data into the table
    cur.execute("""
    INSERT INTO public.todos (id, title, completed) VALUES
    (1, 'get 12 eggs from market', false),
    (2, '1 large bran bread', false),
    (3, '1 stick of salted butter', false),
    (4, '1 kg chicken', false),
    (5, 'biryani masala', false);
    """)
    conn.commit()

    cur.close()
    conn.close()


# Run the database initialization function before starting the Flask app
initialize_database()



# Home page
@app.route('/')
@app.route('/home')
def hello():
    return render_template('home.html', title='Home')


# Todos page
@app.route('/todos')
def todos():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM todos')
    todos = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('todos.html', title='Todos', todos=todos)


# Todo page, cast the todo_id to an integer
@app.route('/todos/<int:todo_id>')
def get_todo_by_id(todo_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(f'SELECT * FROM todos WHERE id = {todo_id}')
    todo = cur.fetchone()
    cur.close()
    conn.close()
    return render_template(
        'todo.html',
        title=f"Todo {todo['id']}",  # type: ignore
        todo=todo)


# Update todo
@app.route('/todos/<int:todo_id>', methods=['POST'])
def update_todo_by_id(todo_id: int):
    # Content-Type must be application/json
    if request.is_json:
        body = request.get_json()
        title = body.get('title')  # type: ignore
        completed = body.get('completed')  # type: ignore

        if title is None:
            return {'message': 'title is required'}, 400

        if completed is None:
            return {'message': 'completed is required'}, 400

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            f"""UPDATE todos SET title = '{title}', completed = {completed}
                        WHERE id = {todo_id}
                    """)

        # If the todo does not exist, return a 404
        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return (f'Todo with id {todo_id} not found', 404)

        conn.commit()
        # Get the updated todo from the database
        cur.execute(f'SELECT * FROM todos WHERE id = {todo_id}')
        todo = cur.fetchone()
        cur.close()
        conn.close()
        return todo or (f'Todo with id {todo_id} not found', 404)
    # if Content-Type is not application/json, return 400
    else:
        return {'message': 'request body must be JSON'}, 400


# Error handler
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# see https://flask.palletsprojects.com/en/2.2.x/templating/#registering-filters
# for more information
# Registering Filter
# Check Line 4 in templates/todos.html to see how to use this filter
@app.template_filter('json_dump')
def json_dump_filter(data):
    return json.dumps(data)


# if __name__ == '__main__':
#     app.run(host="0.0.0.0", port=8000, debug=True)
