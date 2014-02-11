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
from hamcrest import has_item
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

from nti.assessment.submission import QuestionSubmission
from nti.assessment.submission import QuestionSetSubmission
from nti.assessment.submission import AssignmentSubmission


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
				assert_that(entries, is_(4))

				book = grades_interfaces.IGradeBook(course)
				assert_that(book, has_key('default'))
				part = book['default']
				assert_that(part, has_length(1))

				assert_that(book, has_key('quizzes'))
				part = book['quizzes']
				assert_that(part, has_length(2))

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
				assert_that(result, has_length(4))
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
					assert_that( asgs, has_length(4))
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

	@WithSharedApplicationMockDS(users=('harp4162', 'user@not_enrolled'),testapp=True,default_authenticate=True)
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

		sum_link =  self.require_link_href_with_rel(res.json_body, 'GradeSubmittedAssignmentHistorySummaries')
		self.testapp.get(sum_link, extra_environ=instructor_environ)

		# We can filter to just enrolled, which will exclude us
		sum_res = self.testapp.get(sum_link, {'filter': 'LegacyEnrollmentStatusForCredit'}, extra_environ=instructor_environ)
		assert_that( sum_res.json_body, has_entry( 'TotalItemCount', 1 ) )
		assert_that( sum_res.json_body, has_entry( 'TotalNonNullItemCount', 1 ) )
		assert_that( sum_res.json_body, has_entry( 'FilteredTotalItemCount', 0) )
		assert_that( sum_res.json_body, has_entry( 'Items', has_length(0)))

		# Or we can filter to just open, which will include us
		sum_res = self.testapp.get(sum_link, {'filter': 'LegacyEnrollmentStatusOpen'}, extra_environ=instructor_environ)
		assert_that( sum_res.json_body, has_entry( 'TotalItemCount', 1 ) )
		assert_that( sum_res.json_body, has_entry( 'TotalNonNullItemCount', 1 ) )
		assert_that( sum_res.json_body, has_entry( 'FilteredTotalItemCount', 1) )
		assert_that( sum_res.json_body, has_entry( 'Items', has_length(1)))

		bulk_link = self.require_link_href_with_rel(res.json_body, 'GradeSubmittedAssignmentHistory')
		res = self.testapp.get(bulk_link, extra_environ=instructor_environ)

		assert_that( res.json_body, has_entry( 'TotalItemCount', 1 ) )
		assert_that( res.json_body, has_entry( 'FilteredTotalItemCount', 1) )
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
		book_res = res = self.testapp.get(book_path,  extra_environ=instructor_environ)
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
		final_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/no_submit/Final Grade/'
		path = final_grade_path + 'sjohnson@nextthought.com'
		grade['value'] = 75
		res = self.testapp.put_json( path, grade, extra_environ=instructor_environ )
		__traceback_info__ = res.json_body
		final_assignment_id = res.json_body['AssignmentId']

		# And it is now in the gradebook part...
		path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/no_submit/'
		res = self.testapp.get(path,  extra_environ=instructor_environ)
		assert_that( res.json_body,
					 has_entry( 'Items',
								has_entry( 'Final Grade',
										   has_entries( 'Class', 'GradeBookEntry',
														'MimeType', 'application/vnd.nextthought.gradebook.gradebookentry',
														'Items', has_entry( self.extra_environ_default_user.lower(),
																			has_entry( 'value', 75 ))))))

		# ...as well as the student's history (for both the instructor and professor)
		for env in instructor_environ, {}:
			history_res = self.testapp.get(history_path,  extra_environ=env)
			assert_that( history_res.json_body, has_entry('Items', has_entry(final_assignment_id,
																			 has_entry( 'Grade',
																						has_entry( 'value', 75 )))))

			# Both of them can leave feedback on it
			history_feedback_container_href = history_res.json_body['Items'][final_assignment_id]['Feedback']['href']

			from nti.app.assessment.feedback import UsersCourseAssignmentHistoryItemFeedback
			feedback = UsersCourseAssignmentHistoryItemFeedback(body=['Some feedback'])
			ext_feedback = to_external_object(feedback)
			__traceback_info__ = ext_feedback
			res = self.testapp.post_json( history_feedback_container_href,
										  ext_feedback,
										  extra_environ=env,
										  status=201 )
			history_res = self.testapp.get(history_path,  extra_environ=env)
			assert_that( history_res.json_body, has_entry('Items', has_entry(final_assignment_id,
																			 has_entry('Feedback',
																					   has_entry('Items', has_item(has_entry('body', ['Some feedback'])))))))


		# The instructor cannot do this for users that don't exist...
		self.testapp.put_json( final_grade_path + 'foo@bar', grade, extra_environ=instructor_environ,
							   status=404 )
		# ...or for users not enrolled
		self.testapp.put_json( final_grade_path + 'user@not_enrolled', grade, extra_environ=instructor_environ,
							   status=404 )


		# The instructor can download the gradebook as csv and it has
		# the grade in it
		csv_link = self.require_link_href_with_rel(book_res.json_body, 'ExportContents')
		res = self.testapp.get(csv_link, extra_environ=instructor_environ)
		assert_that( res.content_disposition, is_( 'attachment; filename="contents.csv"'))
		csv_text = 'OrgDefinedId,Main Title Points Grade,Trivial Test Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\nsjohnson@nextthought.com,90,,75,100,#\r\n'
		assert_that( res.text, is_(csv_text))

		# He can filter it to Open and ForCredit subsets
		res = self.testapp.get(csv_link + '?LegacyEnrollmentStatus=Open', extra_environ=instructor_environ)
		assert_that( res.content_disposition, is_( 'attachment; filename="contents.csv"'))
		assert_that( res.text, is_(csv_text))

		res = self.testapp.get(csv_link + '?LegacyEnrollmentStatus=ForCredit', extra_environ=instructor_environ)
		assert_that( res.content_disposition, is_( 'attachment; filename="contents.csv"'))
		csv_text = 'OrgDefinedId,Main Title Points Grade,Trivial Test Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\n'
		assert_that( res.text, is_(csv_text))

	@WithSharedApplicationMockDS(users=('harp4162', 'aaa@nextthought.com'),
								 testapp=True,
								 default_authenticate=True)
	def test_filter_sort_page_history(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		instructor_environ = self._make_extra_environ(username='harp4162')
		instructor_environ[b'HTTP_ORIGIN'] = b'http://janux.ou.edu'

		# Note that our username comes first, but our realname (Madden Jason) comes
		# after (Johnson Steve) so we can test sorting by name
		jmadden_environ = self._make_extra_environ(username='aaa@nextthought.com')
		jmadden_environ[b'HTTP_ORIGIN'] = b'http://janux.ou.edu'

		# Re-enum to pick up instructor; also setup profile names
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			getattr(lib, 'contentPackages')
			from nti.dataserver.users.interfaces import IFriendlyNamed
			from nti.dataserver.users import User
			IFriendlyNamed(User.get_user('sjohnson@nextthought.com')).realname = 'Steve Johnson'
			IFriendlyNamed(User.get_user('aaa@nextthought.com')).realname = 'Jason Madden'

		qs_submission = QuestionSetSubmission(questionSetId=self.question_set_id)
		submission = AssignmentSubmission(assignmentId=self.assignment_id, parts=(qs_submission,))

		ext_obj = to_external_object( submission )
		del ext_obj['Class']

		# Make sure we're all enrolled
		for uname, env in (('sjohnson@nextthought.com',None),
						   ('harp4162', instructor_environ),
						   ('aaa@nextthought.com', jmadden_environ)):
			self.testapp.post_json( '/dataserver2/users/'+uname+'/Courses/EnrolledCourses',
									'CLC 3403',
									extra_environ=env,
									status=201 )

		# Now both students submit
		for uname, env in (('sjohnson@nextthought.com',None),
						   ('aaa@nextthought.com', jmadden_environ)):

			self.testapp.post_json( '/dataserver2/Objects/' + self.assignment_id,
									ext_obj,
									extra_environ=env,
									status=201)

		# Check that it should show up in the counter
		res = self.testapp.get('/dataserver2/Objects/' + self.assignment_id, extra_environ=instructor_environ)
		assert_that( res.json_body, has_entry( 'GradeSubmittedCount', 2 ))

		sum_link =  self.require_link_href_with_rel(res.json_body, 'GradeSubmittedAssignmentHistorySummaries')
		self.testapp.get(sum_link, extra_environ=instructor_environ)

		# Sorting requires filtering. Default is ascending for realname
		sum_res = self.testapp.get(sum_link,
								   {'filter': 'LegacyEnrollmentStatusOpen', 'sortOn': 'realname'},
								   extra_environ=instructor_environ)
		assert_that( sum_res.json_body, has_entry( 'TotalItemCount', 2 ) )
		assert_that( sum_res.json_body, has_entry( 'TotalNonNullItemCount', 2 ) )
		assert_that( sum_res.json_body, has_entry( 'FilteredTotalItemCount', 2) )
		assert_that( sum_res.json_body, has_entry( 'Items', has_length(2)))
		assert_that( [x[0] for x in sum_res.json_body['Items']],
					 is_(['sjohnson@nextthought.com', 'aaa@nextthought.com']))

		sum_res = self.testapp.get(sum_link,
								   {'filter': 'LegacyEnrollmentStatusOpen',
									'sortOn': 'realname',
									'sortOrder': 'descending'},
								   extra_environ=instructor_environ)
		assert_that( sum_res.json_body, has_entry( 'Items', has_length(2)))
		assert_that( [x[0] for x in sum_res.json_body['Items']],
					 is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))

		sum_res = self.testapp.get(sum_link,
								   {'filter': 'LegacyEnrollmentStatusOpen',
									'sortOn': 'realname',
									'sortOrder': 'descending',
									'batchSize': 1,
									'batchStart': 0},
								   extra_environ=instructor_environ)
		assert_that( sum_res.json_body, has_entry( 'Items', has_length(1)))
		assert_that( [x[0] for x in sum_res.json_body['Items']],
					 is_(['aaa@nextthought.com']))



	@WithSharedApplicationMockDS(users=('harp4162',),testapp=True,default_authenticate=True)
	def test_instructor_grade_stops_student_submission(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		# Re-enum to pick up instructor
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			getattr(lib, 'contentPackages')

		# Make sure we're enrolled
		res = self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
									  'CLC 3403',
									  status=201 )

		instructor_environ = self._make_extra_environ(username='harp4162')
		instructor_environ[b'HTTP_ORIGIN'] = b'http://janux.ou.edu'

		# The instructor must also be enrolled, as that's how permissioning is setup right now
		self.testapp.post_json( '/dataserver2/users/harp4162/Courses/EnrolledCourses',
								'CLC 3403',
								status=201,
								extra_environ=instructor_environ)

		# If the instructor puts in a grade for something that the student could ordinarily
		# submit...
		trivial_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial Test/'
		path = trivial_grade_path + 'sjohnson@nextthought.com'
		grade = {'Class': 'Grade'}
		grade['value'] = 10
		self.testapp.put_json(path, grade, extra_environ=instructor_environ)

		# ... the student can no longer submit
		assignment_id = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.trivial_test"
		qs_id1 = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset1"
		qs_id2 = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset2"
		question_id1 = "tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.1"
		question_id2 = "tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.2"

		qs1_submission = QuestionSetSubmission(questionSetId=qs_id1, questions=(QuestionSubmission(questionId=question_id1, parts=[0]),))
		qs2_submission = QuestionSetSubmission(questionSetId=qs_id2, questions=(QuestionSubmission(questionId=question_id2, parts=[0,1]),))

		submission = AssignmentSubmission(assignmentId=assignment_id, parts=(qs1_submission, qs2_submission))

		ext_obj = to_external_object( submission )

		res = self.testapp.post_json( '/dataserver2/Objects/' + assignment_id,
								ext_obj,
								status=422)
		assert_that( res.json_body, has_entry('message', "Assignment already submitted"))
		assert_that( res.json_body, has_entry('code', "NotUnique"))


	@WithSharedApplicationMockDS(users=('harp4162'),testapp=True,default_authenticate=True)
	def test_20_autograde_policy(self):
		# This only works in the OU environment because that's where the purchasables are
		extra_env = self.testapp.extra_environ or {}
		extra_env.update( {b'HTTP_ORIGIN': b'http://janux.ou.edu'} )
		self.testapp.extra_environ = extra_env

		# Re-enum to pick up instructor
		with mock_dataserver.mock_db_trans(self.ds):
			lib = component.getUtility(IContentPackageLibrary)
			del lib.contentPackages
			getattr(lib, 'contentPackages')

		# XXX: Dirty registration of an autograde policy
		from ..autograde_policies import TrivialFixedScaleAutoGradePolicy
		component.provideUtility(TrivialFixedScaleAutoGradePolicy(), name="tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice")

		assignment_id = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.trivial_test"
		qs_id1 = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset1"
		qs_id2 = "tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset2"
		question_id1 = "tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.1"
		question_id2 = "tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.2"

		# Get one correct and one incorrect
		qs1_submission = QuestionSetSubmission(questionSetId=qs_id1, questions=(QuestionSubmission(questionId=question_id1, parts=[0]),))
		# The incorrect one is partially correct on parts, but the whole thing is still graded wrong
		qs2_submission = QuestionSetSubmission(questionSetId=qs_id2, questions=(QuestionSubmission(questionId=question_id2, parts=[0,1]),))


		submission = AssignmentSubmission(assignmentId=assignment_id, parts=(qs1_submission, qs2_submission))

		ext_obj = to_external_object( submission )
		del ext_obj['Class']
		assert_that( ext_obj, has_entry( 'MimeType', 'application/vnd.nextthought.assessment.assignmentsubmission'))
		# Make sure we're enrolled
		self.testapp.post_json( '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
								'CLC 3403',
								status=201 )

		self.testapp.post_json( '/dataserver2/Objects/' + assignment_id,
								ext_obj,
								status=201)
		history_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses/CLC 3403/AssignmentHistories/sjohnson@nextthought.com'
		history_res = self.testapp.get( history_path )
		# We were half right
		assert_that( history_res.json_body['Items'].values(),
					 contains( has_entry( 'Grade', has_entries( 'value', 10.0,
																'AutoGrade', 10.0))) )
