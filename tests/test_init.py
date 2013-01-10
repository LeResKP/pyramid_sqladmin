import unittest
from webtest import TestApp
from pyramid import testing
import sqlalchemy as sa
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    clear_mappers,
    )
from zope.sqlalchemy import ZopeTransactionExtension
from sqla_declarative.declarative import extended_declarative_base
import transaction
import pyramid_sqladmin as pysqla
import tw2.core as twc


class TestInit(unittest.TestCase):

    def setUp(self):
        clear_mappers()
        pysqla.AVAILABLE_OBJECTS = pysqla._marker
        self.session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
        Base = extended_declarative_base(
            self.session,
            metadata=sa.MetaData('sqlite:///:memory:'))

        class Test1(Base):
            id = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(50))

        class Test2(Base):
            idtest = sa.Column(sa.Integer, primary_key=True)
            name = sa.Column(sa.String(50))

        Base.metadata.create_all()

        self.Test1 = Test1
        self.Test2 = Test2
        with transaction.manager:
            self.value1 = Test1(name='Bob')
            self.session.add(self.value1)
            self.value2 = Test2(name='Bob')
            self.session.add(self.value2)

    def tearDown(self):
        transaction.abort()

    def test_get_mapped_classes(self):
        result = pysqla.get_mapped_classes()
        self.assertEqual(len(result), 2)
        self.assertEqual(result['test1'], self.Test1)
        self.assertEqual(result['test2'], self.Test2)

    def test_get_class(self):
        self.assertEqual(pysqla.get_class('unexisting'), None)
        self.assertEqual(pysqla.get_class('test1'), self.Test1)

    def test_get_obj(self):
        info = {'match': {
            'classname': '',
            'id': '',
            }}
        result = pysqla.get_obj(info)
        self.assertEqual(result, None)

        info = {'match': {
            'classname': 'test1',
            'id': 1,
            }}
        result = pysqla.get_obj(info)
        obj = self.Test1.query.get(1)
        self.assertEqual(result, obj)

        info = {'match': {
            'classname': 'test1',
            'id': 10,
            }}
        result = pysqla.get_obj(info)
        self.assertEqual(result, None)

        info = {'match': {
            'classname': 'unexisting',
            'id': 1,
            }}
        result = pysqla.get_obj(info)
        self.assertEqual(result, None)

    def test_exist_object(self):
        info = {'match': {
            'classname': 'unexisting',
            'id': 1,
            }}
        self.assertEqual(pysqla.exist_object(info, None), False)

        info = {'match': {
            'classname': 'test1',
            'id': 1,
            }}
        self.assertEqual(pysqla.exist_object(info, None), True)
        obj = self.Test1.query.get(1)
        self.assertEqual(info['match']['cls_or_obj'], obj)

    def test_exist_class(self):
        info = {'match': {
            'classname': 'unexisting',
            }}
        self.assertEqual(pysqla.exist_class(info, None), False)

        info = {'match': {
            'classname': 'test1',
            }}
        self.assertEqual(pysqla.exist_class(info, None), True)
        self.assertEqual(info['match']['cls_or_obj'], self.Test1)

    def test_admin_factory(self):
        request = testing.DummyRequest()
        request.matchdict['cls_or_obj'] = self.Test1
        cls = pysqla.admin_factory(request)
        self.assertEqual(cls.__acl__, [('Allow', 'role:admin', 'admin')])

    def test_home(self):
        request = testing.DummyRequest()
        request.route_url = lambda *args, **kw: 'http://server/%s' % kw['classname']
        response = pysqla.home(request)
        expected = {
            'links': [('Test1', 'http://server/test1'),
                      ('Test2', 'http://server/test2')]
        }
        self.assertEqual(response, expected)

    def test_admin_list(self):
        request = testing.DummyRequest()
        self.Test1.view_all = classmethod(lambda *args, **kw: 'view all')
        response = pysqla.admin_list(self.Test1, request)
        expected = {'html': 'view all'}
        self.assertEqual(response, expected)

    def test_GET_add_or_update(self):
        class MockForm(object):
            value = None
            def display(self):
                s = 'display form'
                if self.value:
                    s += ' with some values'
                return s

        request = testing.DummyRequest()
        self.Test1.edit_form = classmethod(lambda *args, **kw: MockForm())
        response = pysqla.add_or_update(self.Test1, request)
        expected = {'html': 'display form'}
        self.assertEqual(response, expected)

        response = pysqla.add_or_update(self.Test1.query.get(1), request)
        expected = {'html': 'display form with some values'}
        self.assertEqual(response, expected)

    def test_POST_add_or_update(self):
        class MockForm(object):
            value = None
            def display(self):
                s = 'display form'
                if self.value:
                    s += ' with some values'
                return s
            def validate(self, data):
                return data

        request = testing.DummyRequest()
        request.route_url = lambda *args, **kw: (
            'http://server/%s/%s' % (kw['classname'], kw['id']))
        request.POST = {'name': 'Fred'}
        request.method = 'POST'
        self.Test1.edit_form = classmethod(lambda *args, **kw: MockForm())
        response = pysqla.add_or_update(self.Test1, request)
        self.assertEqual(response.status, '302 Found')
        self.assertTrue(
            ('Location',
            'http://server/test1/2')
            in response._headerlist)
        self.assertEqual(self.Test1.query.get(1).name, 'Bob')
        self.assertEqual(self.Test1.query.get(2).name, 'Fred')

        response = pysqla.add_or_update(self.Test1.query.get(1), request)
        self.assertEqual(response.status, '302 Found')
        self.assertTrue(
            ('Location',
            'http://server/test1/1')
            in response._headerlist)
        self.assertEqual(self.Test1.query.get(1).name, 'Fred')
        self.assertEqual(self.Test1.query.count(), 2)

    def test_fail_POST_add_or_update(self):
        class MockForm(object):
            value = None
            def display(self):
                s = 'display form'
                if self.value:
                    s += ' with some values'
                return s
            def validate(self, data):
                raise twc.ValidationError('Validation error', widget=self)

        request = testing.DummyRequest()
        request.POST = {'name': 'Fred'}
        request.method = 'POST'
        form = MockForm()
        self.Test1.edit_form = classmethod(lambda *args, **kw: form)
        response = pysqla.add_or_update(self.Test1, request)
        expected = {'html': 'display form'}
        self.assertEqual(response, expected)

        form.value = request.POST
        response = pysqla.add_or_update(self.Test1.query.get(1), request)
        expected = {'html': 'display form with some values'}
        self.assertEqual(response, expected)
        self.assertEqual(self.Test1.query.get(1).name, 'Bob')


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        clear_mappers()
        pysqla.AVAILABLE_OBJECTS = pysqla._marker
        self.config = testing.setUp()
        self.config.include(pysqla)

    def tearDown(self):
        testing.tearDown()

    def test_url(self):
        request = testing.DummyRequest()
        url = request.route_url('admin_home')
        expected = 'http://example.com/admin'
        self.assertEqual(url, expected)

        url = request.route_url('admin_list', classname='test1')
        expected = 'http://example.com/admin/test1'
        self.assertEqual(url, expected)

        url = request.route_url('admin_new', classname='test1')
        expected = 'http://example.com/admin/test1/new'
        self.assertEqual(url, expected)

        url = request.route_url('admin_edit', classname='test1', id=1)
        expected = 'http://example.com/admin/test1/1/edit'
        self.assertEqual(url, expected)


