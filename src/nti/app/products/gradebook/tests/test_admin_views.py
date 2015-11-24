#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_entries
does_not = is_not

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

class TestAdminViews(ApplicationLayerTest):

	layer = InstructedCourseApplicationTestLayer

	default_origin = str('http://janux.ou.edu')

	course_ntiid = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'

	@WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
	def test_synchronize_gradebook(self):
		environ = self._make_extra_environ()
		environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

		res = self.testapp.post_json('/dataserver2/@@SynchronizeGradebook',
									 {'ntiid': self.course_ntiid},
									 extra_environ=environ,
									 status=200)
		assert_that(res.json_body, has_entry('Items',
											has_entries('default',  [u'Main Title'],
														'no_submit', [u'Final Grade'],
														 'quizzes' , [u'Main Title', u'Trivial Test'])))
