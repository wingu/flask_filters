"""
Tests for flask_filters.
"""

from nose.tools import eq_, ok_

from flask import abort, Flask
from flask.ext import filters
from werkzeug.exceptions import NotFound


flask_app = Flask(__name__)


# YIELD A VALUE TO ABORT REQUEST

def abort_filter():
    yield 'This is an error message.'
    ok_(False)  # we shouldn't get here

@filters.make_filter(abort_filter)
def aborted_view():
    ok_(False)  # we shouldn't get here

def test_abort_request():
    with flask_app.test_request_context('/'):
        response = aborted_view()
        eq_(response, 'This is an error message.')
        eq_([], filters.get_filters_before_run())


# YIELD A VALUE TO REPLACE RESPONSE

def response_filter():
    yield
    yield 'Hello, world! This is a replaced response.'

@filters.make_filter(response_filter)
def replaced_response_view():
    return 'The filter should replace this message with "Hello, world!"'

def test_replaced_response():
    with flask_app.test_request_context('/'):
        response = replaced_response_view()
        eq_(response, 'Hello, world! This is a replaced response.')
        eq_([response_filter], filters.get_filters_before_run())
        eq_([response_filter], filters.get_filters_after_run())


# DO NOT CHANGE THE RESPONSE IF YIELD SENDS NONE

def noop_filter():
    yield None
    yield

@filters.make_filter(noop_filter)
def hello_world_view():
    return "Hello, world! It's a fabulous day."

def test_unmodified_response():
    with flask_app.test_request_context('/'):
        response = hello_world_view()
        eq_(response, "Hello, world! It's a fabulous day.")
        eq_([noop_filter], filters.get_filters_before_run())
        eq_([noop_filter], filters.get_filters_after_run())


# APPLY MULTIPLE FILTERS IN THE CORRECT ORDER

@filters.apply_filters(noop_filter, abort_filter, response_filter)
def multiple_filter_view():
    return 'This view has multiple filters.'

def test_multiple_filters():
    with flask_app.test_request_context('/'):
        response = multiple_filter_view()
        eq_(response, 'This is an error message.')
        eq_([noop_filter], filters.get_filters_before_run())


# APPLY FILTERS CORRECTLY USING VIEW DECORATOR

def another_noop_filter():
    yield
    yield None
    ok_(False)  # we shouldn't get here

_view = filters.make_view_decorator(flask_app, '/',
                                    noop_filter, another_noop_filter)

@_view('', 'GET')
def reusable_decorator_view():
    return 'This view is wrapped with a reusable view decorator.'

@_view('one_off', 'GET', filters=[response_filter])
def one_off_filter_view():
    return 'This view adds a one-off filter to a reusable decorator.'

def test_reusable_decorator():
    with flask_app.test_request_context('/'):
        response = reusable_decorator_view()
        eq_(response, 'This view is wrapped with a reusable view decorator.')
        eq_([noop_filter, another_noop_filter],
            filters.get_filters_before_run())
        eq_([another_noop_filter, noop_filter],
            filters.get_filters_after_run())
    with flask_app.test_request_context('/one_off'):
        response = one_off_filter_view()
        eq_(response, 'Hello, world! This is a replaced response.')
        eq_([response_filter, noop_filter, another_noop_filter],
            filters.get_filters_before_run())
        eq_([another_noop_filter, noop_filter, response_filter],
            filters.get_filters_after_run())
