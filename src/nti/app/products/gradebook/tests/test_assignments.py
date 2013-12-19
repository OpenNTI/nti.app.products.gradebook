#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
from hamcrest import is_not
does_not = is_not
from hamcrest import has_entry

import os

from zope import component
from zope import interface

from nti.contentlibrary.interfaces import IContentPackageLibrary
from nti.contentlibrary.filesystem import CachedNotifyingStaticFilesystemLibrary as Library

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.app.products.gradebook import assignments
from nti.app.products.gradebook import interfaces as grades_interfaces

from nti.app.testing.application_webtest import SharedApplicationTestBase
from nti.app.testing.decorators import WithSharedApplicationMockDS

import pyramid.interfaces

from nti.dataserver.tests import mock_dataserver
from nti.externalization.tests import externalizes
from nti.externalization.externalization import to_external_object

class TestAssignments(SharedApplicationTestBase):

	@classmethod
	def _setup_library(cls, *args, **kwargs):
		lib = Library(
					paths=(os.path.join(
								   os.path.dirname(__file__),
								   'Library',
								   'CLC3403_LawAndJustice'),
				   ))
		return lib

	@mock_dataserver.WithMockDSTrans
	def test_synchronize_gradebook(self):

		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			for package in lib.contentPackages:
				course = ICourseInstance(package)
				entries = assignments.synchronize_gradebook(course)
				assert_that(entries, is_(2))

				book = grades_interfaces.IGradeBook(course)
				assert_that(book, has_key('default'))
				part = book['default']
				assert_that(part, has_length(1))

				assert_that(book, has_key('quizzes'))
				part = book['quizzes']
				assert_that(part, has_length(1))

				assert_that( part, has_key('Main Title'))

	@mock_dataserver.WithMockDSTrans
	def test_get_course_assignments(self):

		base = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.assignment%s"
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			for package in lib.contentPackages:
				course = ICourseInstance(package)
				result = assignments.get_course_assignments(course, sort=True, reverse=True)
				assert_that(result, has_length(2))
				for idx, a in enumerate(result):
					ntiid = base % (len(result) - idx)
					assert_that(a, has_property('ntiid', is_(ntiid)))

					# No request means no links
					assert_that( a, externalizes( does_not( has_key( 'GradeSubmittedCount' ))))

			# Now create a request as the instructor and check
			# that the extra data is there
			self._create_user('harp4162')
			# re-enumerate to pick up the user
			del lib.contentPackages

			request = self.beginRequest()
			request.environ['REMOTE_USER'] = 'harp4162'
			# XXX: NOTE: This is unclean
			class Policy(object):
				interface.implements( pyramid.interfaces.IAuthenticationPolicy )
				def authenticated_userid( self, request ):
					return 'harp4162'
				def effective_principals(self, request):
					return ['harp4162']

			old = component.getUtility(pyramid.interfaces.IAuthenticationPolicy)
			request.registry.registerUtility( Policy() )

			for package in lib.contentPackages:
				course = ICourseInstance(package)
				asgs = assignments.get_course_assignments(course)
				assert_that( asgs, has_length(2))
				for asg in asgs:
					assert_that( asg, externalizes( has_entry( 'GradeSubmittedCount', 0 )))
					ext = to_external_object(asg)
					href = self.require_link_href_with_rel(ext, 'GradeSubmittedAssignmentHistory')
					assert_that( href, is_( '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/%s/Main%%20Title/SubmittedAssignmentHistory'
											% asg.category_name))
			request.registry.registerUtility( old )

	assignment_id = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.assignment1"
	question_set_id = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:ASMT1_ichigo"

	@WithSharedApplicationMockDS(users=('harp4162'),testapp=True,default_authenticate=True)
	def test_instructor_access_to_history_items(self):
		# Re-enum to pick up instructor
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			getattr(lib, 'contentPackages')
		from nti.assessment.submission import QuestionSetSubmission
		from nti.assessment.submission import AssignmentSubmission
		qs_submission = QuestionSetSubmission(questionSetId=self.question_set_id)
		submission = AssignmentSubmission(assignmentId=self.assignment_id, parts=(qs_submission,))

		ext_obj = to_external_object( submission )
		del ext_obj['Class']
		assert_that( ext_obj, has_entry( 'MimeType', 'application/vnd.nextthought.assessment.assignmentsubmission'))
		# Make sure we're enrolled
		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'CLC 3403',
									  status=201 )

		self.testapp.post_json( '/dataserver2/Objects/' + self.assignment_id,
								ext_obj,
								status=201)

		instructor_environ = self._make_extra_environ(username='harp4162')

		# The instructor must also be enrolled, as that's how permissioning is setup right now
		self.testapp.post_json( '/dataserver2/users/harp4162/Courses/EnrolledCourses',
								'CLC 3403',
								status=201,
								extra_environ=instructor_environ)
		# First, it should show up in the counter
		res = self.testapp.get('/dataserver2/Objects/' + self.assignment_id, extra_environ=instructor_environ)
		assert_that( res.json_body, has_entry( 'GradeSubmittedCount', 1 ))

		bulk_link = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/%s/Main%%20Title/SubmittedAssignmentHistory'
		res = self.testapp.get(bulk_link, extra_environ=instructor_environ, status=404)
