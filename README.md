# flask_filters

The `flask_filters` module helps you wrap [Flask][] views with coroutine filters.  The bundled `hello_world.py` application demonstrates most of this module's functionality.

[Flask]: http://flask.pocoo.org/ (Flask is a web development microframework for Python)


## Installation

If you have a fairly recent version of `pip`, install `flask_filters` system-wide using:

    pip install git+https://github.com/wingu/flask_filters

or locally, to a [virtualenv][] named `flask_env`:

    pip install -E flask_env git+https://github.com/wingu/flask_filters

Otherwise, install Flask, then clone this git repository and install from `setup.py`:

    git clone https://github.com/wingu/flask_filters
    cd flask_filters; python setup.py install


### Dependencies

* Python 2.5+ (primarily tested with Python 2.7, not compatible with Python 3)
* [Flask][]
* The bundled Hello World app uses Flask's jsonify method, which relies on [simplejson][] for Python 2.5. (`simplejson` was added to the standard library as the `json` module in Python 2.6.)

[simplejson]: http://pypi.python.org/pypi/simplejson (simplejson is a fast and extensible JSON encoder/decoder for Python)


## Defining Filters

Filters are implemented as coroutines.  Yielding nothing hands control to the next filter or view function; yielding anything not-None stops filtering and uses that something as the response data.  Filters must yield at least once when run.

    def auth_filter():
        if not is_logged_in():
            yield abort(401)
        yield
        do_some_logging_after()

After yielding, filters are provided the result of the view function and can inspect the response.  If the filter yields a second time, yielding anything not-None replaces the view's original response, but does not stop filtering -- the remaining filters are run with the new response.

    def heading_filter():
        data = yield
        yield '<h1>%s</h1>' % data

Filter coroutines are closed after a second yield.  Filters that yield exactly once, or filters that yield None on the second iteration, do not alter the view's return value.


## Applying Filters

You can directly wrap a single view function with a list of filters using an extra decorator:

    @flask_app.route('/hello/world')
    @apply_filters(auth_filter, heading_filter)
    def hello_world():
        return 'Hello world!'

In this case, the `hello_world` view is wrapped by `heading_filter`, and then that result is wrapped by `auth_filter`.  Thus, the execution flows like this:

    # Start in auth_filter()
    if not is_logged_in():
        abort(401)
    
    # Yield to heading_filter()
    # Which in turn yields to hello_world(), which returns a response:
    response = 'Hello world!'
    
    # hello_world()'s response is sent back to heading_filter(),
    # which yields a modified response
    data = response
    response = '<h1>%s</h1>' % data
    
    # And finally, the response is sent back to auth_filter
    # auth_filter does not change the response
    do_some_logging_after()
    
    return response

That means `auth_filter` will execute before `heading_filter`, then `hello_world` will render the view as usual.  Finally, `heading_filter` gets to finish its work before `auth_filter`.


## Reducing Repetition

Most of the time, you'll probably want to apply a consistent set of filters to several views in the same URL namespace of your application.  Don't just copy and paste the same `@apply_filters` decorator everywhere!  You can create a reusable decorator for a set of filters with `make_view_decorator`:

    _view = make_view_decorator(flask_app, '/hello/', auth_filter, heading_filter)
    
    @_view('world')
    def hello_world():
        return 'Hello world!'
    
    @_view('mother')
    def hello_mother():
        return 'Hi, mom!'


## More Complex Applications

Sometimes you want a reusable decorator, but you also need to add an extra filter to one of your views.  Never despair, we've got your back!  You can easily add more filters that wrap around the filters listed on a custom view decorator:

    _view = make_view_decorator(flask_app, '/hello/', auth_filter)
    
    @_view('world', filters=[heading_filter])
    def hello_world():
        return 'Hello world!'

But watch out!  This time, `hello_world` is wrapped by `auth_filter`, and that result is wrapped by `heading_filter`.  Previously, the two filters executed in the opposite order.  Here's how you can keep `auth_filter` in a reusable decorator and add `heading_filter` in the same sequence as our previous examples:

    _view = make_view_decorator(flask_app, '/hello/', auth_filter)
    
    @_view('world')
    @apply_filters(heading_filter)
    def hello_world():
        return 'Hello world!'


## Miscellaneous Notes

If you are using Flask's blueprints, you can provide a blueprint anywhere this module expects a Flask application.

`get_filters_before_run()` returns a list of filters that have successfully pre-processed the current request before the decorated view function is run (i.e. until the filter coroutine's first yield).  Similarly, `get_filters_after_run()` returns a list of filters that have post-processed the current request's response from the decorated view function.  These lists can be useful for writing unit tests.


## Development
