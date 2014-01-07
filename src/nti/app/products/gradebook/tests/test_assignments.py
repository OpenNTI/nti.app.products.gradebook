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
from hamcrest import has_entries
from hamcrest import contains

import os
import urllib
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
			from zope.component.interfaces import IComponents
			from nti.app.products.courseware.interfaces import ICourseCatalog
			components = component.getUtility(IComponents, name='platform.ou.edu')
			catalog = components.getUtility( ICourseCatalog )
			# XXX
			# This test is unclean, we re-register globally
			global_catalog = component.getUtility(ICourseCatalog)
			global_catalog._entries[:] = catalog._entries

			for package in lib.contentPackages:
				course = ICourseInstance(package)
				entries = assignments.synchronize_gradebook(course)
				assert_that(entries, is_(3))

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

		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			getattr(lib, 'contentPackages')
			from zope.component.interfaces import IComponents
			from nti.app.products.courseware.interfaces import ICourseCatalog
			components = component.getUtility(IComponents, name='platform.ou.edu')
			catalog = components.getUtility( ICourseCatalog )
			# XXX
			# This test is unclean, we re-register globally
			global_catalog = component.getUtility(ICourseCatalog)
			global_catalog._entries[:] = catalog._entries

			for package in lib.contentPackages:
				course = ICourseInstance(package)
				result = assignments.get_course_assignments(course, sort=True, reverse=True)
				assert_that(result, has_length(3))
				for a in result:
					# No request means no links
					assert_that( a, externalizes( does_not( has_key( 'GradeSubmittedCount' ))))

			# Now create a request as the instructor and check
			# that the extra data is there
			self._create_user('harp4162')
			# re-enumerate to pick up the user
			del lib.contentPackages
			del global_catalog._entries[:]
			getattr(lib, 'contentPackages')
			# XXX
			# This test is unclean, we re-register globally
			global_catalog = component.getUtility(ICourseCatalog)
			global_catalog._entries[:] = catalog._entries

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
			component.provideUtility( Policy() )
			try:
				for package in lib.contentPackages:
					course = ICourseInstance(package)
					asgs = assignments.get_course_assignments(course)
					assert_that( asgs, has_length(3))
					for asg in asgs:
						assert_that( asg, externalizes( has_entry( 'GradeSubmittedCount', 0 )))
						ext = to_external_object(asg)
						href = self.require_link_href_with_rel(ext, 'GradeSubmittedAssignmentHistory')
						title = asg.title
						title = urllib.quote(title)
						assert_that( href, is_( '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/%s/%s/SubmittedAssignmentHistory'
												% (asg.category_name, title)))
			finally:
				component.provideUtility( old, provides=pyramid.interfaces.IAuthenticationPolicy )
				assert_that( component.getUtility(pyramid.interfaces.IAuthenticationPolicy),
							 is_(old) )

	assignment_id = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.assignment1"
	question_set_id = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:ASMT1_ichigo"

	@WithSharedApplicationMockDS(users=('harp4162'),testapp=True,default_authenticate=True)
	def test_instructor_access_to_history_items_edit_grade(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

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
		# The student has no edit link for the grade
		history_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses/CLC 3403/AssignmentHistories/sjohnson@nextthought.com'
		history_res = self.testapp.get( history_path )
		assert_that( history_res.json_body['Items'].values(),
					 contains( has_entry( 'Grade', has_entry( 'Links', [] ))) )


		instructor_environ = self._make_extra_environ(username='harp4162')
		instructor_environ[b'HTTP_ORIGIN'] = b'http://janux.ou.edu'

		# The instructor must also be enrolled, as that's how permissioning is setup right now
		self.testapp.post_json( '/dataserver2/users/harp4162/Courses/EnrolledCourses',
								'CLC 3403',
								status=201,
								extra_environ=instructor_environ)
		# First, it should show up in the counter
		res = self.testapp.get('/dataserver2/Objects/' + self.assignment_id, extra_environ=instructor_environ)
		assert_that( res.json_body, has_entry( 'GradeSubmittedCount', 1 ))

		bulk_link = self.require_link_href_with_rel(res.json_body, 'GradeSubmittedAssignmentHistory')
		res = self.testapp.get(bulk_link, extra_environ=instructor_environ)

		assert_that( res.json_body, has_entry( 'Items', has_length(1)))
		assert_that( res.json_body, has_entry( 'Items', has_key(self.extra_environ_default_user.lower())))
		assert_that( res.json_body['Items'][self.extra_environ_default_user.lower()],
					 has_key('Grade'))
		assert_that( res.json_body, has_entry( 'href', is_(bulk_link)))

		grade = res.json_body['Items'][self.extra_environ_default_user.lower()]['Grade']
		grade_edit = self.require_link_href_with_rel(grade, 'edit')
		assert_that( grade, has_entry( 'value', None ))
		grade['value'] = 90
		self.testapp.put_json(grade_edit, grade, extra_environ=instructor_environ)

		res = self.testapp.get(bulk_link, extra_environ=instructor_environ)
		grade = res.json_body['Items'][self.extra_environ_default_user.lower()]['Grade']
		assert_that( grade, has_entry( 'value', 90 ))

		# The instructor can find that same grade in the part when fetched directly...
		part_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes'
		res = self.testapp.get(part_path,  extra_environ=instructor_environ)
		assert_that( res.json_body,
					 has_entry( 'Items',
								has_entry( 'Main Title',
										   has_entries( 'AssignmentId', self.assignment_id,
														'Items', has_entry( self.extra_environ_default_user.lower(),
																			has_entry( 'value', 90 ))))))

		# ...or through the book
		book_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook'
		res = self.testapp.get(book_path,  extra_environ=instructor_environ)
		assert_that( res.json_body,
					 has_entry( 'Items',
								has_entry('quizzes',
										  has_entry( 'Items',
													 has_entry( 'Main Title',
																has_entries( 'AssignmentId', self.assignment_id,
																			 'Items', has_entry( self.extra_environ_default_user.lower(),
																								 has_entry( 'value', 90 ))))))))

		# And in the student's history, visible to both
		for env in instructor_environ, {}:
			res = self.testapp.get(history_path,  extra_environ=env)
			assert_that( res.json_body, has_entry('Items', has_entry(self.assignment_id,
																	 has_entry( 'Grade',
																				has_entry( 'value', 90 )))))

		# A non-submittable part can be directly graded by the professor
		path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/no_submit/Final Grade/sjohnson@nextthought.com'
		grade['value'] = 75
		res = self.testapp.put_json( path, grade, extra_environ=instructor_environ )
		__traceback_info__ = res.json_body
		final_assignment_id = res.json_body['AssignmentId']

		# And it is now in the part
		path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/no_submit/'
		res = self.testapp.get(path,  extra_environ=instructor_environ)
		assert_that( res.json_body,
					 has_entry( 'Items',
								has_entry( 'Final Grade',
										   has_entries( 'Class', 'GradeBookEntry',
														'MimeType', 'application/vnd.nextthought.gradebook.gradebookentry',
														'Items', has_entry( self.extra_environ_default_user.lower(),
																			has_entry( 'value', 75 ))))))

		# as well as the student's history
		for env in instructor_environ, {}:
			res = self.testapp.get(history_path,  extra_environ=env)
			assert_that( res.json_body, has_entry('Items', has_entry(final_assignment_id,
																	 has_entry( 'Grade',
																				has_entry( 'value', 75 )))))
