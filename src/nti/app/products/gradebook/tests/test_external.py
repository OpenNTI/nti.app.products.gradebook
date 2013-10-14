#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from nti.externalization import externalization

from .. import grades
from nti.testing.base import SharedConfiguringTestBase

import nti.dataserver.tests.mock_dataserver as mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from hamcrest import assert_that
from hamcrest import is_
from hamcrest import has_key
from hamcrest import has_entry

class TestExternal(SharedConfiguringTestBase):

	set_up_packages = ('nti.dataserver', 'nti.app.products.gradebook')

	@WithMockDSTrans
	def test_grade(self):
		g = grades.Grade(entry="quiz1", grade=85.0, autograde=80.2)
		externalization.to_external_object(g)
		print(g)
