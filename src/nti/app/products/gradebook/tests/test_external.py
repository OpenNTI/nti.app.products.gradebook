#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

import random

from nti.externalization import externalization
from nti.externalization import internalization

from .. import grades
from nti.testing.base import SharedConfiguringTestBase

from hamcrest import (assert_that, none, is_, is_not, has_entry, has_property)

class TestExternal(SharedConfiguringTestBase):

	set_up_packages = ('nti.dataserver', 'nti.app.products.gradebook')

	def test_grade(self):
		g = grades.Grade(entry="quiz1", grade=85.0, autograde=80.2)
		ext = externalization.to_external_object(g)
		assert_that(ext, has_entry(u'Class', 'Grade'))
		assert_that(ext, has_entry(u'grade', is_(85.0)))
		assert_that(ext, has_entry(u'entry', 'quiz1'))
		assert_that(ext, has_entry(u'autograde', is_(80.2)))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.grade'))
		assert_that(ext, has_entry(u'Last Modified', is_not(none())))

		factory = internalization.find_factory_for(ext)
		newgrade = factory()
		internalization.update_from_external_object(newgrade, ext)
		assert_that(newgrade, has_property('entry', 'quiz1'))
		assert_that(newgrade, has_property('grade', is_(85.0)))
		assert_that(newgrade, has_property('autograde', is_(80.2)))

	def test_grades(self):
		count = 0
		store = grades.Grades()
		r = random.randint(5, 15)
		for _ in range(r):
			username = 'u%s' % random.randint(1, 5)
			entry = 'e%s' % random.randint(1, 5)
			grade = grades.Grade(entry=entry, 
								 grade=float(random.randint(1, 100)),
								 autograde=float(random.randint(1, 100)))
			if store.index(username, grade) == -1:
				count += 1
				store.add_grade(username, grade)

		ext = externalization.to_external_object(store)
		assert_that(ext, has_entry(u'Class', 'Grades'))
		assert_that(ext, has_entry(u'MimeType', 'application/vnd.nextthought.grades'))
		new_count = 0
		for lst in ext.get('Items', {}).values():
			new_count += len(lst)
		assert_that(new_count, is_(count))

		factory = internalization.find_factory_for(ext)
		new_store = factory()
		internalization.update_from_external_object(new_store, ext)

		assert_that(len(store), is_(len(new_store)))
		for username in store.keys():
			for grade in store.get_grades(username):
				new_grade = new_store.find_grade(username, grade)
				assert_that(new_grade, is_not(none()))
				assert_that(new_grade, has_property('grade', grade.grade))
				assert_that(new_grade, has_property('autograde'), is_(grade.autograde))
		
