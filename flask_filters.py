"""
Support for view filters in Flask.


DEFINING FILTERS

Filters are implemented as coroutines.  Yielding nothing hands control to the
next filter or view function; yielding anything not-None stops filtering and
uses that something as the response data.  Filters must yield at least once
when run.

  >>> def my_filter():
  >>>     if not is_logged_in():
  >>>         yield abort(401)
  >>>     yield
  >>>     do_some_logging_after()

After yielding, filters are provided the result of the view function and can
inspect the response.  If the filter yields a second time, yielding anything
not-None replaces the view's original response, but does not stop filtering --
the remaining filters are run with the new response.

  >>> def heading_filter():
  >>>     data = yield
  >>>     yield '<h1>%s</h1>' % data

Filter coroutines are closed after a second yield.  Filters that yield exactly
once, or filters that yield None on the second iteration, do not alter the
view's return value.


APPLYING FILTERS

There are two different approaches to applying these filters to your
application's views.  You can directly wrap a single view function with a list
of filters using an extra decorator:

  >>> @flask_app.route('/hello/world')
  >>> @apply_filters(my_filter)
  >>> def hello_world():
  >>>     return 'Hello world!'

But most of the time, you'll probably want to apply a consistent set of filters
to several views in the same URL namespace of your application.  Don't just
copy and paste that decorator all over your code!  You can create a reusable
decorator for a set of filters with make_view_decorator.  This example is
functionally identical to the previous one:

  >>> _view = make_view_decorator(flask_app, '/hello/', my_filter)
  >>> @_view('world')
  >>> def hello_world():
  >>>     return 'Hello world!'


OTHER NOTES

If you are using Flask's blueprints, you can provide a blueprint anywhere
this module expects a Flask application.

get_filters_before_run() returns a list of filters that have successfully
pre-processed the current request before the decorated view function is run
(i.e. until the filter coroutine's first yield).  Similarly,
get_filters_after_run() returns a list of filters that have post-processed
the current request's response from the decorated view function.  These lists
can be useful for writing unit tests.

"""

import functools

from flask import g


def make_view_decorator(flask_app, base_url, *filters):
    """
    Returns a decorator to register a view function for a URL route.

    This is an extension of @flask_app.route (where flask_app is a flask
    application or blueprint), adding support for filters that wrap a view
    function.

    The returned decorator function takes a path (relative to `base_url`) and
    one or more HTTP methods (GET, POST, etc.).

    You can also provide a list of additional filters to run for only the 
    decorated function.  Those filters will run "outside" the filters listed
    in the call to make_view_decorator -- that is, view-specific filters will
    be the first filters to run before the view function and the last filters
    to run after the view.
    """
    def decorator(path, *methods, **options):
        """
        Decorator to register a view function for a URL route.

        The only valid keyword argument is 'filters', which must be an iterable
        of filters that should be prepended to the 
        """
        if options and options.keys() != ['filters']:
            extra_kwargs_set = set(options.keys()) - set(['filters'])
            extra_kwargs = ', '.join(extra_kwargs_set)
            raise TypeError('unexpected keyword argument(s): %s' % extra_kwargs)

        decorators = [flask_app.route(base_url + path, methods=methods)]
        filter_list = []
        if 'filters' in options:
            filter_list.extend(options['filters'])
        if filters:
            filter_list.extend(filters)
        if filter_list:
            decorators.append(apply_filters(*filter_list))
        return combine_decorators(decorators)

    return decorator


def apply_filters(*view_filters):
    """
    Decorator that applies a list of coroutine filters to a view function.

    The leftmost argument is the first one to run before a request and the last
    one to run after -- i.e. the leftmost argument is the outermost filter.
    """
    filter_decorators = [make_filter(fn) for fn in view_filters]
    return combine_decorators(filter_decorators)


def has_filter_before_run(filter_func):
    """
    Return true if the "before" portion of the specified filter func
    has already run, else false.
    """
    return filter_func in get_filters_before_run()


def has_filter_after_run(filter_func):
    """
    Return true if the "after" portion of the specified filter func
    has already run, else false.
    """
    return filter_func in get_filters_after_run()


def get_filters_after_run():
    """
    Get the filters whose "after" part has run.
    """
    return _get_filter_run_record()['after']


def get_filters_before_run():
    """
    Get the filters whose "before" part has run.
    """
    return _get_filter_run_record()['before']


# Low-level implementation.
# The following API is usually uninteresting for users of this module.

def make_filter(filter_func):
    """
    Turns a generator function into a decorator for views. The decorator runs
    the generator function up to its first yield, then runs the view function,
    then runs the rest of the generator function. If the first yield returns
    something other than none, that is used as the response and the view
    function/rest of the generator are not called. Generators are sent the
    result of the view function, so doing e.g. "response = yield" provides the
    generator a way to inspect the response.
    """

    def decorator(decorated_func):
        """
        A decorator for view functions that runs the generator as a filter of
        the view.
        """
        @functools.wraps(decorated_func)
        def decorated(*args, **kwargs):
            """
            The wrapped function, which implements wrapping a view function
            with a generator function.
            """
            gen = filter_func()
            try:
                filter_result = gen.send(None)
                if filter_result is not None:
                    return filter_result
            except StopIteration:
                raise RuntimeError('filter must yield at least once')

            _mark_filter_before_run(filter_func)
            result = decorated_func(*args, **kwargs)
            try:
                filter_result = gen.send(result)
                if filter_result is not None:
                    result = filter_result
                gen.close()
            except StopIteration:
                pass
            _mark_filter_after_run(filter_func)
            return result
        return decorated

    return decorator


def combine_decorators(decorators):
    """
    Combines a sequence of decorators into a new decorator. The first decorator
    is the outermost, same as with Python's syntax. As in,

    @combine_decorators(a, b, c)
    def some_function():
        pass

    is equivalent to

    @a
    @b
    @c
    def some_function():
        pass
    """
    return reduce(_compose_decorators, reversed(decorators))


def _compose_decorators(inner, outer):
    """
    Composes decorators for use with reduce(). The inner one is applied to the
    function first.
    """
    return lambda fn: outer(inner(fn))


def _get_filter_run_record():
    """
    Get the request scoped record of which filters have run their
    before and after.

    This isn't intended for use outside this module.  Use
    has_filter_(before|after)_run or get_filters_(before|after)_run
    instead.
    """
    if not hasattr(g, 'filter_run_record') or not g.filter_run_record:
        g.filter_run_record = {'before': [], 'after': []}
    return g.filter_run_record


def _mark_filter_before_run(filter_func):
    """
    Mark that the "before" portion of a filter has run.
    """
    _get_filter_run_record()['before'].append(filter_func)


def _mark_filter_after_run(filter_func):
    """
    Mark that the "after" portion of a filter has run.
    """
    _get_filter_run_record()['after'].append(filter_func)
