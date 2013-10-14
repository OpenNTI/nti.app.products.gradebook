#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.externalization import externalization

from nti.app.products.gradebook import grades
from nti.app.products.gradebook.tests import ConfiguringTestBase

import nti.dataserver.tests.mock_dataserver as mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from hamcrest import (assert_that, is_, is_not, has_length, none, has_property)

class TestExternal(ConfiguringTestBase):

	@WithMockDSTrans
	def test_grade(self):
		g = grades.Grade(entry="quiz1", grade=85.0, autograde=80.2)
		externalization.to_external_object(g)
		print(g)
