"""
Hello, World!  In Flask, with filters.
"""
from flask import Flask
from flask import abort, g, jsonify
from flask.ext.filters import apply_filters, make_view_decorator


# Create a Flask application.
flask_app = Flask(__name__)


def hello_world_filter():
    """
    Filter that sets a request-global message to 'Hello, world!'
    """
    g.message = 'Hello, world!'
    yield


def json_filter():
    """
    Filter that wraps a Flask view that returns a Python dict and serializes
    that dict as JSON.

    Refuses to run after hello_world_filter.
    """
    if hasattr(g, 'message') and g.message:
        yield abort(418)
    data = yield
    yield jsonify(data)


# Create a decorator that registers view functions against flask_app in the
# root URL namespace, and also wraps each view with hello_world_filter
_view = make_view_decorator(flask_app, '/', hello_world_filter)


@_view('', 'GET')
def hello_world():
    """
    Displays a simple HTML "Hello, world!"

    Order of execution:
    1. The hello_world_filter sets g.message to "Hello, world!", then yields.
    2. This view runs, returning a dict.
    3. The hello_world_filter resumes (and does nothing).
    """
    html_links = '''<p><a href="/json">JSON</a></p>
                    <p><a href="/error">error</a></p>'''
    return g.message + html_links


@_view('json', 'GET', filters=[json_filter])
def hello_world_json():
    """
    Returns a JSON object with the message: "Hello, world!"

    Order of execution:
    1. The json_filter checks for g.message, then yields.
    2. The hello_world_filter sets g.message to "Hello, world!", then yields.
    3. This view runs, returning a dict.
    4. The hello_world_filter resumes (and does nothing).
    5. The json_filter resumes, then yields a JSON-serialized copy of the dict
       that replaces the view's response.
    """
    return dict(message=g.message)


@_view('error', 'GET')
@apply_filters(json_filter)
def hello_world_error():
    """
    Displays an error page.

    Order of execution:
    1. The hello_world_filter sets g.message to "Hello, world!", then yields.
    2. The json_filter sees that g.message is already set, so it aborts the
       request with HTTP 418: "I'm a teapot".
    """
    return dict(message=g.message)


# Start the application in debug mode when running this script directly.
if __name__ == '__main__':
    flask_app.run(debug=True)
