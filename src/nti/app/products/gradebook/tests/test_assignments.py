#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import greater_than
from hamcrest import contains_inanyorder
does_not = is_not

import fudge

from nti.testing.time import time_monotonically_increases

from six.moves import urllib_parse

from zope import component
from zope import interface
from zope import lifecycleevent

from pyramid.interfaces import IAuthenticationPolicy

from nti.app.contenttypes.completion import COMPLETION_POLICY_VIEW_NAME
from nti.app.contenttypes.completion import COMPLETION_REQUIRED_VIEW_NAME

from nti.app.products.gradebook import assignments
from nti.app.products.gradebook import interfaces as grades_interfaces

from nti.assessment.interfaces import IQAssignment
from nti.assessment.submission import QuestionSubmission
from nti.assessment.submission import QuestionSetSubmission
from nti.assessment.submission import AssignmentSubmission

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer

from nti.contenttypes.completion.policies import CompletableItemAggregateCompletionPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.dataserver.tests import mock_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.externalization.tests import externalizes

COURSE_NTIID = u'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'


class TestAssignments(ApplicationLayerTest):

    layer = InstructedCourseApplicationTestLayer

    default_origin = 'http://janux.ou.edu'

    @WithSharedApplicationMockDS
    def test_synchronize_gradebook(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

            lib = component.getUtility(IContentPackageLibrary)

            law_course = None
            for package in lib.contentPackages:
                course = ICourseInstance(package)
                if course.__name__ == 'CLC3403':
                    law_course = course

                entries = assignments.synchronize_gradebook(course)
                assert_that(entries, is_(4))

                book = grades_interfaces.IGradeBook(course)
                assert_that(book, has_key('default'))
                part = book['default']
                assert_that(part, has_length(1))

                assert_that(book, has_key('quizzes'))
                part = book['quizzes']
                assert_that(part, has_length(2))

                assert_that(part, has_key('Main Title'))

            # Changing the title changes the display name, but
            # not the key

            asg = component.getUtility(IQAssignment,
                                       name="tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.assignment1")
            assert_that(asg.title, is_('Main Title'))

            try:
                asg.title = u'New Title'
                assignments.synchronize_gradebook(law_course)
                book = grades_interfaces.IGradeBook(law_course)
                part = book['quizzes']
                entry = part['Main Title']
                assert_that(entry, has_property('displayName', 'New Title'))
            finally:
                asg.title = u'Main Title'

    @WithSharedApplicationMockDS
    def test_get_course_assignments(self):

        with mock_dataserver.mock_db_trans(self.ds, site_name='platform.ou.edu'):

            lib = component.getUtility(IContentPackageLibrary)

            for package in lib.contentPackages:
                course = ICourseInstance(package)
                result = assignments.get_course_assignments(course, sort=True,
                                                            reverse=True)
                assert_that(result, has_length(4))
                for a in result:
                    assert_that(a,
                                externalizes(does_not(has_key('GradeSubmittedCount'))))

            request = self.beginRequest()
            request.environ['REMOTE_USER'] = 'harp4162'

            # XXX: NOTE: This is unclean
            from zope.security._definitions import system_user

            @interface.implementer(IAuthenticationPolicy)
            class Policy(object):

                def authenticated_userid(self, unused_request):
                    return 'harp4162'

                def effective_principals(self, unused_request):
                    return ['harp4162']

                interaction = None
                principal = system_user

            old = component.getUtility(IAuthenticationPolicy)
            component.provideUtility(Policy())
            from zope.security.management import newInteraction, endInteraction
            newInteraction(Policy())
            try:
                for package in lib.contentPackages:
                    course = ICourseInstance(package)
                    asgs = assignments.get_course_assignments(course)
                    assert_that(asgs, has_length(4))
                    for asg in asgs:
                        assert_that(asg,
                                    externalizes(has_entry('GradeSubmittedCount', 0)))
                        ext = to_external_object(asg)
                        self.require_link_href_with_rel(ext,
                                                        'GradeBookByAssignment')
                        href = self.require_link_href_with_rel(ext,
                                                               'GradeSubmittedAssignmentHistory')
                        title = asg.title
                        title = urllib_parse.quote(title)
                        assert_that(href,
                                    is_('/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/%s/%s/SubmittedAssignmentHistory'
                                        % (asg.category_name, title)))
            finally:
                component.provideUtility(old, provides=IAuthenticationPolicy)
                assert_that(component.getUtility(IAuthenticationPolicy),
                            is_(old))
                endInteraction()

    assignment_id = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.assignment1"
    question_set_id = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:ASMT1_ichigo"

    @WithSharedApplicationMockDS(users=('user@not_enrolled'), testapp=True, default_authenticate=True)
    def test_instructor_access_to_history_items_edit_grade(self):
        # This only works in the OU environment because that's where the
        # purchasables are
        extra_env = self.testapp.extra_environ or {}
        extra_env.update({'HTTP_ORIGIN': 'http://janux.ou.edu'})
        self.testapp.extra_environ = extra_env

        qs_submission = QuestionSetSubmission(questionSetId=self.question_set_id)
        submission = AssignmentSubmission(assignmentId=self.assignment_id,
                                          parts=(qs_submission,))
        submit_href = '/dataserver2/Objects/%s?ntiid=%s' % (self.assignment_id, COURSE_NTIID)

        ext_obj = to_external_object(submission)
        del ext_obj['Class']
        assert_that(ext_obj,
                    has_entry('MimeType', 'application/vnd.nextthought.assessment.assignmentsubmission'))

        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        # submit
        assignment_res = self.testapp.get(submit_href)
        start_href = self.require_link_href_with_rel(assignment_res.json_body,
                                                     'Commence')
        self.testapp.post(start_href)
        res = self.testapp.post_json(submit_href, ext_obj, status=201)
        history_path = self.require_link_href_with_rel(res.json_body, 'AssignmentHistoryItem')

        # The student has no edit link for the grade
        history_res = self.testapp.get(history_path)
        history_item = history_res.json_body
        assert_that(history_item,
                    has_entry('Grade', has_entry('Links', has_length(1))))

        # because this grade was not auto-graded, the student has no notable
        # mention of it
        notable_res = self.fetch_user_recursive_notable_ugd()
        assert_that(notable_res.json_body, has_entry('TotalItemCount', 0))

        instructor_environ = self._make_extra_environ(username='harp4162')
        instructor_environ['HTTP_ORIGIN'] = 'http://janux.ou.edu'

        # First, it should show up in the counter
        res = self.testapp.get('/dataserver2/Objects/' + self.assignment_id,
                               extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('GradeSubmittedCount', 1))

        self.require_link_href_with_rel(res.json_body, 'GradeBookByAssignment')
        sum_link = self.require_link_href_with_rel(res.json_body,
                                                  'GradeSubmittedAssignmentHistorySummaries')
        assert_that(sum_link,
                    is_('/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Main%20Title/SubmittedAssignmentHistorySummaries'))

        self.testapp.get(sum_link, extra_environ=instructor_environ)

        bulk_link = self.require_link_href_with_rel(
            res.json_body, 'GradeSubmittedAssignmentHistory')
        assert_that(bulk_link,
                    is_('/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Main%20Title/SubmittedAssignmentHistory'))

        # We can walk it down to just one user
        res = self.testapp.get(sum_link + '/' + self.extra_environ_default_user.lower())
        assert_that(res.json_body,
                    has_entry('Class', 'UsersCourseAssignmentHistoryItemSummary'))
        res = self.testapp.get(bulk_link + '/' + self.extra_environ_default_user.lower())
        assert_that(res.json_body,
                    has_entry('Class', 'UsersCourseAssignmentHistoryItem'))

        # We can filter to just enrolled, which will exclude us
        sum_res = self.testapp.get(sum_link, {'filter': 'LegacyEnrollmentStatusForCredit'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('TotalItemCount', 1))
        assert_that(sum_res.json_body, has_entry('TotalNonNullItemCount', 1))
        assert_that(sum_res.json_body, has_entry('FilteredTotalItemCount', 0))
        assert_that(sum_res.json_body, has_entry('Items', has_length(0)))

        # Or we can filter to just open, which will include us
        sum_res = self.testapp.get(sum_link, {
                                   'filter': 'LegacyEnrollmentStatusOpen'}, extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('TotalItemCount', 1))
        assert_that(sum_res.json_body, has_entry('TotalNonNullItemCount', 1))
        assert_that(sum_res.json_body, has_entry('FilteredTotalItemCount', 1))
        assert_that(sum_res.json_body, has_entry('Items', has_length(1)))

        res = self.testapp.get(bulk_link, extra_environ=instructor_environ)

        assert_that(res.json_body, has_entry('TotalItemCount', 1))
        assert_that(res.json_body, has_entry('FilteredTotalItemCount', 1))
        assert_that(res.json_body, has_entry('Items', has_length(1)))
        assert_that(res.json_body,
                    has_entry('Items', has_key(self.extra_environ_default_user.lower())))
        assert_that(res.json_body['Items'][self.extra_environ_default_user.lower()],
                    has_key('Grade'))
        assert_that(res.json_body, has_entry('href', is_(bulk_link)))

        grade = res.json_body['Items'][self.extra_environ_default_user.lower()]['Grade']
        grade_edit = self.require_link_href_with_rel(grade, 'edit')
        assert_that(grade, has_entry('value', None))
        grade['value'] = 90
        self.testapp.put_json(grade_edit, grade,
                              extra_environ=instructor_environ)

        res = self.testapp.get(bulk_link, extra_environ=instructor_environ)
        grade = res.json_body['Items'][self.extra_environ_default_user.lower()]['Grade']
        assert_that(grade, has_entry('value', 90))

        # The instructor can find that same grade in the part when fetched
        # directly...
        part_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes'
        res = self.testapp.get(part_path,  extra_environ=instructor_environ)
        assert_that(res.json_body,
                    has_entry('Items',
                              has_entry('Main Title',
                                        has_entries('AssignmentId', self.assignment_id,
                                                    'Items', has_entry(self.extra_environ_default_user.lower(),
                                                                       has_entry('value', 90))))))

        # ...or through the book
        book_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook'
        res = self.testapp.get(book_path,  extra_environ=instructor_environ)
        assert_that(res.json_body,
                    has_entry('Items',
                              has_entry('quizzes',
                                        has_entry('Items',
                                                  has_entry('Main Title',
                                                            has_entries('AssignmentId', self.assignment_id,
                                                                        'Items', has_entry(self.extra_environ_default_user.lower(),
                                                                                           has_entry('value', 90))))))))

        # And in the student's history, visible to both
        for env in instructor_environ, {}:
            res = self.testapp.get(history_path, extra_environ=env)
            assert_that(res.json_body, has_entry('Grade', has_entry('value', 90)))

        # A non-submittable part can be directly graded by the professor
        final_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/no_submit/Final Grade/'
        path = final_grade_path + 'sjohnson@nextthought.com'
        grade['value'] = "75 -"  # Use a string like the app typically sends
        res = self.testapp.put_json(path, grade,
                                    extra_environ=instructor_environ)
        __traceback_info__ = res.json_body
        final_href = self.require_link_href_with_rel(res.json_body, 'AssignmentHistoryItem')

        # And it is now in the gradebook part...
        path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/no_submit/'
        res = self.testapp.get(path,  extra_environ=instructor_environ)
        assert_that(res.json_body,
                    has_entry('Items',
                              has_entry('Final Grade',
                                        has_entries('Class', 'GradeBookEntry',
                                                    'MimeType', 'application/vnd.nextthought.gradebook.gradebookentry',
                                                    'Items', has_entry(self.extra_environ_default_user.lower(),
                                                                       has_entry('value', "75 -"))))))

        # ...as well as the student's history (for both the instructor and professor)
        for env in instructor_environ, {}:
            history_res = self.testapp.get(final_href, extra_environ=env)
            assert_that(history_res.json_body,
                        has_entries('Grade', has_entry('value', "75 -"),
                                             'SyntheticSubmission', True))

            # Both of them can leave feedback on it
            history_feedback_container_href = history_res.json_body['Feedback']['href']

            from nti.app.assessment.feedback import UsersCourseAssignmentHistoryItemFeedback
            feedback = UsersCourseAssignmentHistoryItemFeedback(
                body=[u'Some feedback']
            )
            ext_feedback = to_external_object(feedback)
            __traceback_info__ = ext_feedback
            res = self.testapp.post_json(history_feedback_container_href,
                                         ext_feedback,
                                         extra_environ=env,
                                         status=201)
            history_res = self.testapp.get(final_href, extra_environ=env)
            assert_that(history_res.json_body,
                         has_entry('Feedback', has_entry('Items', has_item(has_entry('body', ['Some feedback'])))))

        # The instructor cannot do this for users that don't exist...
        self.testapp.put_json(final_grade_path + 'foo@bar', grade, extra_environ=instructor_environ,
                              status=404)
        # ...or for users not enrolled
        self.testapp.put_json(final_grade_path + 'user@not_enrolled', grade, extra_environ=instructor_environ,
                              status=404)

        # The instructor can download the gradebook as csv and it has the
        # grade in it.
        # setup profile names
        with mock_dataserver.mock_db_trans(self.ds):
            from nti.dataserver.users.interfaces import IFriendlyNamed
            prof = IFriendlyNamed(User.get_user('sjohnson@nextthought.com'))
            prof.realname = u'Steve Johnson\u0107'
            lifecycleevent.modified(prof.__parent__)

        # Our links are now off of a GradeBook shell in the course
        course_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
        course_res = self.testapp.get(course_path,
                                      extra_environ=instructor_environ)
        gradebook_json = course_res.json_body.get('GradeBook')
        csv_link = self.require_link_href_with_rel(gradebook_json,
                                                   'ExportContents')
        res = self.testapp.get(csv_link, extra_environ=instructor_environ)
        assert_that(res.content_disposition,
                    is_('attachment; filename="CLC3403_full-grades.csv"'))
        csv_text = u'Username,External ID,First Name,Last Name,Full Name,Main Title Points Grade,Trivial Test Points Grade,Main Title Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\nsjohnson@nextthought.com,sjohnson@nextthought.com,Steve,Johnson\u0107,Steve Johnson\u0107,90,,,75,100,#\r\n'
        assert_that(res.text, is_(csv_text))

        # He can filter it to Open and ForCredit subsets
        res = self.testapp.get(csv_link + '?LegacyEnrollmentStatus=Open',
                               extra_environ=instructor_environ)
        assert_that(res.content_disposition,
                    is_('attachment; filename="CLC3403_Open-grades.csv"'))
        assert_that(res.text, is_(csv_text))

        res = self.testapp.get(csv_link + '?LegacyEnrollmentStatus=ForCredit',
                               extra_environ=instructor_environ)
        assert_that(res.content_disposition,
                    is_('attachment; filename="CLC3403_ForCredit-grades.csv"'))
        csv_text = 'Username,External ID,First Name,Last Name,Full Name,Main Title Points Grade,Trivial Test Points Grade,Main Title Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\n'
        assert_that(res.text, is_(csv_text))

    @WithSharedApplicationMockDS(users=('aaa@nextthought.com'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_download_sorting(self):
        # This only works in the OU environment because that's where the
        # purchasables are
        extra_env = self.testapp.extra_environ or {}
        extra_env.update({'HTTP_ORIGIN': 'http://janux.ou.edu'})
        self.testapp.extra_environ = extra_env

        instructor_environ = self._make_extra_environ(username='harp4162')
        instructor_environ['HTTP_ORIGIN'] = 'http://janux.ou.edu'

        # Note that our username comes first, but our realname (Madden Jason) comes
        # after (Johnson Steve) so we can test sorting by name
        jmadden_environ = self._make_extra_environ(username='aaa@nextthought.com')
        jmadden_environ['HTTP_ORIGIN'] = 'http://janux.ou.edu'

        #  setup profile names
        with mock_dataserver.mock_db_trans(self.ds):
            from nti.dataserver.users.interfaces import IFriendlyNamed

            prof = IFriendlyNamed(User.get_user('sjohnson@nextthought.com'))
            prof.realname = u'Steve Johnson'
            # get both the user and the profile in the index with this
            # updated data
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
            prof = IFriendlyNamed(User.get_user('aaa@nextthought.com'))
            prof.realname = u'Jason Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)

        qs_submission = QuestionSetSubmission(questionSetId=self.question_set_id)
        submission = AssignmentSubmission(assignmentId=self.assignment_id,
                                          parts=(qs_submission,))
        submit_href = '/dataserver2/Objects/%s?ntiid=%s' % (self.assignment_id, COURSE_NTIID)

        ext_obj = to_external_object(submission)
        del ext_obj['Class']

        # Enroll default student
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)
        # Enroll second student
        self.testapp.post_json('/dataserver2/users/aaa@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201,
                               extra_environ=jmadden_environ)

        # submit for both students
        assignment_res = self.testapp.get(submit_href)
        start_href = self.require_link_href_with_rel(assignment_res.json_body,
                                                     'Commence')
        self.testapp.post(start_href)
        self.testapp.post_json(submit_href, ext_obj, status=201)
        assignment_res = self.testapp.get(submit_href, extra_environ=jmadden_environ)
        start_href = self.require_link_href_with_rel(assignment_res.json_body,
                                                     'Commence')
        self.testapp.post(start_href, extra_environ=jmadden_environ)
        self.testapp.post_json(submit_href, ext_obj,
                               status=201,
                               extra_environ=jmadden_environ)

        # Our links are now off of a GradeBook shell in the course
        course_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
        course_res = self.testapp.get(course_path,
                                      extra_environ=instructor_environ)
        gradebook_json = course_res.json_body.get('GradeBook')
        csv_link = self.require_link_href_with_rel(gradebook_json,
                                                  'ExportContents')
        res = self.testapp.get(csv_link, extra_environ=instructor_environ)
        csv_text = 'Username,External ID,First Name,Last Name,Full Name,Main Title Points Grade,Trivial Test Points Grade,Main Title Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\nsjohnson@nextthought.com,sjohnson@nextthought.com,Steve,Johnson,Steve Johnson,,,,0,100,#\r\naaa@nextthought.com,aaa@nextthought.com,Jason,Madden,Jason Madden,,,,0,100,#\r\n'
        assert_that(res.text, is_(csv_text))

        #  If we switch names, they should still be sorted correctly.
        with mock_dataserver.mock_db_trans(self.ds):
            prof = IFriendlyNamed(User.get_user('sjohnson@nextthought.com'))
            prof.realname = u'Jason Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
            prof = IFriendlyNamed(User.get_user('aaa@nextthought.com'))
            prof.realname = u'Steve Johnson'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)

        # download the gradebook again and check that the sorting is correct
        res = self.testapp.get(csv_link, extra_environ=instructor_environ)
        csv_text = 'Username,External ID,First Name,Last Name,Full Name,Main Title Points Grade,Trivial Test Points Grade,Main Title Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\naaa@nextthought.com,aaa@nextthought.com,Steve,Johnson,Steve Johnson,,,,0,100,#\r\nsjohnson@nextthought.com,sjohnson@nextthought.com,Jason,Madden,Jason Madden,,,,0,100,#\r\n'
        assert_that(res.text, is_(csv_text))

        # If both users have the same last name, should be sorted by first name.
        # If both have a last name of Madden, then Jason should come before
        # Steve.
        with mock_dataserver.mock_db_trans(self.ds):
            prof = IFriendlyNamed(User.get_user('sjohnson@nextthought.com'))
            prof.realname = u'Steve Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
            prof = IFriendlyNamed(User.get_user('aaa@nextthought.com'))
            prof.realname = u'Jason Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
        res = self.testapp.get(csv_link, extra_environ=instructor_environ)
        csv_text = u'Username,External ID,First Name,Last Name,Full Name,Main Title Points Grade,Trivial Test Points Grade,Main Title Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\naaa@nextthought.com,aaa@nextthought.com,Jason,Madden,Jason Madden,,,,0,100,#\r\nsjohnson@nextthought.com,sjohnson@nextthought.com,Steve,Madden,Steve Madden,,,,0,100,#\r\n'
        assert_that(res.text, is_(csv_text))

        # Switch names from the above scenario to make sure they're actually
        # being sorted
        with mock_dataserver.mock_db_trans(self.ds):
            prof = IFriendlyNamed(User.get_user('sjohnson@nextthought.com'))
            prof.realname = u'Jason Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
            prof = IFriendlyNamed(User.get_user('aaa@nextthought.com'))
            prof.realname = u'Steve Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
        res = self.testapp.get(csv_link, extra_environ=instructor_environ)
        csv_text = 'Username,External ID,First Name,Last Name,Full Name,Main Title Points Grade,Trivial Test Points Grade,Main Title Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\nsjohnson@nextthought.com,sjohnson@nextthought.com,Jason,Madden,Jason Madden,,,,0,100,#\r\naaa@nextthought.com,aaa@nextthought.com,Steve,Madden,Steve Madden,,,,0,100,#\r\n'
        assert_that(res.text, is_(csv_text))

        # If both names are identical, they should be sorted by username.
        with mock_dataserver.mock_db_trans(self.ds):
            prof = IFriendlyNamed(User.get_user('sjohnson@nextthought.com'))
            prof.realname = u'Jason Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
            prof = IFriendlyNamed(User.get_user('aaa@nextthought.com'))
            prof.realname = u'Jason Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
        res = self.testapp.get(csv_link, extra_environ=instructor_environ)
        csv_text = u'Username,External ID,First Name,Last Name,Full Name,Main Title Points Grade,Trivial Test Points Grade,Main Title Points Grade,Adjusted Final Grade Numerator,Adjusted Final Grade Denominator,End-of-Line Indicator\r\naaa@nextthought.com,aaa@nextthought.com,Jason,Madden,Jason Madden,,,,0,100,#\r\nsjohnson@nextthought.com,sjohnson@nextthought.com,Jason,Madden,Jason Madden,,,,0,100,#\r\n'
        assert_that(res.text, is_(csv_text))

    @WithSharedApplicationMockDS(users=('aaa@nextthought.com'),
                                 testapp=True,
                                 default_authenticate=True)
    def test_filter_sort_page_history(self):

        # This only works in the OU environment because that's where the
        # purchasables are
        extra_env = self.testapp.extra_environ or {}
        extra_env.update({'HTTP_ORIGIN': 'http://janux.ou.edu'})
        self.testapp.extra_environ = extra_env

        instructor_environ = self._make_extra_environ(username='harp4162')
        instructor_environ['HTTP_ORIGIN'] = 'http://janux.ou.edu'

        # Note that our username comes first, but our realname (Madden Jason) comes
        # after (Johnson Steve) so we can test sorting by name
        jmadden_environ = self._make_extra_environ(username='aaa@nextthought.com')
        jmadden_environ['HTTP_ORIGIN'] = 'http://janux.ou.edu'

        #  setup profile names
        with mock_dataserver.mock_db_trans(self.ds):
            from nti.dataserver.users.interfaces import IFriendlyNamed

            prof = IFriendlyNamed(User.get_user('sjohnson@nextthought.com'))
            prof.realname = u'Steve Johnson'
            # get both the user and the profile in the index with this
            # updated data
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)
            prof = IFriendlyNamed(User.get_user('aaa@nextthought.com'))
            prof.realname = u'Jason Madden'
            lifecycleevent.modified(prof.__parent__)
            lifecycleevent.modified(prof)

        qs_submission = QuestionSetSubmission(questionSetId=self.question_set_id)
        submission = AssignmentSubmission(assignmentId=self.assignment_id,
                                          parts=(qs_submission,))
        submit_href = '/dataserver2/Objects/%s?ntiid=%s' % (self.assignment_id, COURSE_NTIID)

        ext_obj = to_external_object(submission)
        del ext_obj['Class']

        # Make sure we're all enrolled
        # In the past, the instructor had to also be enrolled, but
        # because permissioning is handled at a lower level now that's not necessary;
        # in fact, it throws counts off
        for uname, env in (('sjohnson@nextthought.com', None),
                           #('harp4162', instructor_environ),
                           ('aaa@nextthought.com', jmadden_environ)):
            self.testapp.post_json('/dataserver2/users/' + uname + '/Courses/EnrolledCourses',
                                   COURSE_NTIID,
                                   extra_environ=env,
                                   status=201)

        # Before we submit, we have no count
        res = self.testapp.get('/dataserver2/Objects/' + self.assignment_id,
                               extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('GradeSubmittedCount', 0))

        sum_link = self.require_link_href_with_rel(res.json_body,
                                                   'GradeSubmittedAssignmentHistorySummaries')
        self.testapp.get(sum_link, extra_environ=instructor_environ)
        # We can request it sorted, even with nothing in it, and it works
        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'feedbackCount'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))
        assert_that([x[1] for x in sum_res.json_body['Items']],
                    is_([None, None]))

        # Now both students submit
        for uname, env in (('sjohnson@nextthought.com', None),
                           ('aaa@nextthought.com', jmadden_environ)):
            assignment_res = self.testapp.get(submit_href, extra_environ=env)
            start_href = self.require_link_href_with_rel(assignment_res.json_body,
                                                         'Commence')
            self.testapp.post(start_href, extra_environ=env)
            self.testapp.post_json(submit_href, ext_obj,
                                   extra_environ=env,
                                   status=201)

        # Check that it should show up in the counter
        res = self.testapp.get('/dataserver2/Objects/' + self.assignment_id,
                               extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('GradeSubmittedCount', 2))
        assert_that(res.json_body,
                    has_entry('GradeAssignmentSubmittedCount', 2))
        sum_link = self.require_link_href_with_rel(res.json_body,
                                                  'GradeSubmittedAssignmentHistorySummaries')
        self.testapp.get(sum_link, extra_environ=instructor_environ)

        # Sorting requires filtering. Default is ascending for realname
        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'realname'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('TotalItemCount', 2))
        assert_that(sum_res.json_body, has_entry('TotalNonNullItemCount', 2))
        assert_that(sum_res.json_body, has_entry('FilteredTotalItemCount', 2))
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    contains_inanyorder('sjohnson@nextthought.com', 'aaa@nextthought.com'))

        # first item, container, first submission
        sj_hist_oid = sum_res.json_body['Items'][0][1]['OID']

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'realname',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'realname',
                                    'usernameSearchTerm': 'Jason'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(1)))
        assert_that(sum_res.json_body, has_entry('FilteredTotalItemCount', 1))
        assert_that(sum_res.json_body, has_entry('TotalItemCount', 2))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'realname',
                                    'sortOrder': 'descending',
                                    'batchSize': 1,
                                    'batchStart': 0},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(1)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'username',
                                    'sortOrder': 'descending',
                                    'batchSize': 1,
                                    'batchStart': 0,
                                    'batchAround': sj_hist_oid},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(1)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'username',
                                    'sortOrder': 'ascending',
                                    'batchSize': 1,
                                    'batchStart': 0,
                                    'batchAround': sj_hist_oid},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(1)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'username',
                                    'sortOrder': 'descending',
                                    'batchSize': 1,
                                    'batchStart': 0,
                                    'batchAroundCreator': 'SJohnson@nextthought.CoM'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(1)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com']))
        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'username',
                                    'sortOrder': 'ascending',
                                    'batchSize': 1,
                                    'batchStart': 0,
                                    'batchAroundCreator': 'SJohnson@nextthought.CoM'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(1)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'dateSubmitted',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'feedbackCount'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'gradeValue'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))
        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'gradeValue',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com', 'aaa@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'username'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'username',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com', 'aaa@nextthought.com']))

        # Submission filtering, with enrollment filtering

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen,HasSubmission',
                                    'sortOn': 'username',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com', 'aaa@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen,NoSubmission',
                                    'sortOn': 'username',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(0)))
        assert_that(sum_res.json_body,
                    has_entry('FilteredTotalItemCount', is_(0)))

        # Submission filtering, without enrollment filtering

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'HasSubmission',
                                    'sortOn': 'username',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['sjohnson@nextthought.com', 'aaa@nextthought.com']))

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'NoSubmission',
                                    'sortOn': 'username',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(0)))
        assert_that(sum_res.json_body,
                    has_entry('FilteredTotalItemCount', is_(0)))

        # If the instructor deletes a grade for a user, the submission date
        # sorting still works and values are still returned

        history_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses/CLC 3403/AssignmentHistories/sjohnson@nextthought.com'
        history_res = self.testapp.get(history_path)

        grade = history_res.json_body['Items']['tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.assignment1']['Items'][0]['Grade']
        self.testapp.delete(grade['href'], extra_environ=instructor_environ)

        sum_res = self.testapp.get(sum_link,
                                   {'filter': 'LegacyEnrollmentStatusOpen',
                                    'sortOn': 'dateSubmitted',
                                    'sortOrder': 'descending'},
                                   extra_environ=instructor_environ)
        assert_that(sum_res.json_body, has_entry('Items', has_length(2)))
        assert_that([x[0] for x in sum_res.json_body['Items']],
                    is_(['aaa@nextthought.com', 'sjohnson@nextthought.com']))
        # sj's submission should not be none
        assert_that(sum_res.json_body['Items'][0][1], is_(not_none()))
        assert_that(sum_res.json_body['Items'][1][1], is_(not_none()))

        res = self.testapp.get('/dataserver2/Objects/' + self.assignment_id,
                               extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('GradeSubmittedCount', 1))
        assert_that(res.json_body,
                    has_entry('GradeAssignmentSubmittedCount', 2))

    @WithSharedApplicationMockDS(users=('jason'), testapp=True, default_authenticate=True)
    def test_instructor_grade_stops_student_submission(self):
        # This only works in the OU environment because that's where the
        # purchasables are
        extra_env = self._make_extra_environ(username='jason')
        extra_env.update({'HTTP_ORIGIN': 'http://janux.ou.edu'})
        self.testapp.extra_environ = extra_env

        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/jason/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        instructor_environ = self._make_extra_environ(username='harp4162')
        instructor_environ['HTTP_ORIGIN'] = 'http://janux.ou.edu'

        # If the instructor puts in a grade for something that the student could ordinarily
        # submit...
        trivial_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial Test/'
        path = trivial_grade_path + 'JaSoN'  # Notice we are mangling the case
        # Note the bad MimeType, but it doesn't matter
        grade = {"MimeType": "application/vnd.nextthought.courseware.grade",
                 "tags": [], "value": "324 -"}
        res = self.testapp.put_json(path, grade,
                                    extra_environ=instructor_environ)
        assert_that(res.json_body,
                    has_entry('MimeType', 'application/vnd.nextthought.grade'))
        assert_that(res.json_body, has_entry('value', '324 -'))

        href = res.json_body['href']
        excuse_ref = href + "/excuse"
        res = self.testapp.post(excuse_ref, extra_environ=instructor_environ,
                                status=200)
        assert_that(res.json_body, has_entry('IsExcused', is_(True)))

        unexcuse_ref = href + "/unexcuse"
        res = self.testapp.post(unexcuse_ref, extra_environ=instructor_environ,
                                status=200)
        assert_that(res.json_body, has_entry('IsExcused', is_(False)))

        # ... the student can no longer submit
        assignment_id = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.trivial_test"
        qs_id1 = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset1"
        qs_id2 = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset2"
        question_id1 = u"tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.1"
        question_id2 = u"tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.2"

        submit_href = '/dataserver2/Objects/%s?ntiid=%s' % (assignment_id, COURSE_NTIID)

        qs1_submission = QuestionSetSubmission(questionSetId=qs_id1,
                                               questions=(QuestionSubmission(questionId=question_id1, parts=[0]),))
        qs2_submission = QuestionSetSubmission(questionSetId=qs_id2,
                                               questions=(QuestionSubmission(questionId=question_id2, parts=[0, 1]),))

        submission = AssignmentSubmission(assignmentId=assignment_id,
                                          parts=(qs1_submission, qs2_submission))

        ext_obj = to_external_object(submission)

        assignment_res = self.testapp.get(submit_href)
        start_href = self.require_link_href_with_rel(assignment_res.json_body,
                                                     'Commence')
        self.testapp.post(start_href)
        res = self.testapp.post_json(submit_href, ext_obj, status=422)
        assert_that(res.json_body,
                    has_entry('message', "Assignment already submitted"))
        assert_that(res.json_body, has_entry('code', "NotUnique"))

        # ... this didn't cause an activity item to be added for the instructor
        activity_link = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/CourseActivity'
        res = self.testapp.get(activity_link, extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('TotalItemCount', 0))

        # and it shows up as a notable item for the student...
        notable_res = self.fetch_user_recursive_notable_ugd(username='jason')
        assert_that(notable_res.json_body, has_entry('TotalItemCount', 1))

        # ... and can be fetched directly
        oid = notable_res.json_body['Items'][0]['OID']

        from nti.ntiids import ntiids

        ntiid = ntiids.make_ntiid(provider='ignored',
                                  specific=oid,
                                  nttype=ntiids.TYPE_OID)
        self.fetch_by_ntiid(ntiid)

    def _set_completion_policy(self, instructor_environ):
        # Course completion policy, 100%
        aggregate_mimetype = CompletableItemAggregateCompletionPolicy.mime_type
        full_data = {u'MimeType': aggregate_mimetype}
        course_res = self.testapp.get('/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403').json_body
        policy_url = self.require_link_href_with_rel(course_res,
                                                     COMPLETION_POLICY_VIEW_NAME)
        return self.testapp.put_json(policy_url, full_data, extra_environ=instructor_environ).json_body

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    @fudge.patch('nti.app.assessment.completion.get_policy_completion_passing_percent')
    @fudge.patch('nti.app.products.gradebook.decorators.get_policy_completion_passing_percent')
    @fudge.patch('nti.app.products.gradebook.completion.get_auto_grade_policy')
    @fudge.patch('nti.app.products.gradebook.decorators.get_auto_grade_policy')
    def test_20_autograde_policy(self, mock_passing_perc, mock_passing_perc2, mock_auto_grade, mock_auto_grade2):
        mock_passing_perc.is_callable().returns(None)
        mock_passing_perc2.is_callable().returns(None)

        def update_passing_perc(value):
            mock_passing_perc.is_callable().returns(value)
            mock_passing_perc2.is_callable().returns(value)

        mock_auto_grade.is_callable().returns({'total_points': 20})
        mock_auto_grade2.is_callable().returns({'total_points': 20})

        # This only works in the OU environment because that's where the
        # purchasables are
        extra_env = self.testapp.extra_environ or {}
        extra_env.update({'HTTP_ORIGIN': 'http://janux.ou.edu'})
        self.testapp.extra_environ = extra_env

        # XXX: Dirty registration of an autograde policy
        from nti.app.products.gradebook.autograde_policies import TrivialFixedScaleAutoGradePolicy
        component.provideUtility(TrivialFixedScaleAutoGradePolicy(),
                                 name="tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.clc_3403_law_and_justice")

        assignment_id = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.trivial_test"
        qs_id1 = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset1"
        qs_id2 = u"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.set.qset:trivial_test_qset2"
        question_id1 = u"tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.1"
        question_id2 = u"tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.naq.qid.ttichigo.2"

        def validate_completion(progress=True, complete=True, success=True, enroll_record_href=None, passing_percentage=None):
            progress_check = not_none if progress else none
            completed_length = 1 if complete else 0
            with mock_dataserver.mock_db_trans(self.ds):
                course = find_object_with_ntiid(COURSE_NTIID)
                course = ICourseInstance(course)
                assignment = find_object_with_ntiid(assignment_id)
                user = User.get_user('sjohnson@nextthought.com')
                progress = component.queryMultiAdapter((user, assignment, course),
                                                       IProgress)
                assert_that(progress, progress_check())

                principal_container = component.queryMultiAdapter((user, course),
                                                                  IPrincipalCompletedItemContainer)
                assert_that(principal_container, not_none())
                assert_that(principal_container, has_length(completed_length))
                if completed_length:
                    completed_item = tuple(principal_container.values())[0]
                    assert_that(completed_item.Success, is_(success))
            if enroll_record_href and complete:
                enroll_res = self.testapp.get(enroll_record_href).json_body
                course_completed_res = enroll_res['CourseProgress'].get('CompletedItem')
                assert_that(course_completed_res, not_none())
                assignment_meta = course_completed_res.get('CompletionMetadata')
                assert_that(assignment_meta, not_none())
                assert_that(assignment_meta['Items'], has_length(1))
                assert_that(assignment_meta['SuccessCount'], is_(1 if success else 0))
                assert_that(assignment_meta['FailCount'], is_(1 if not success else 0))
                assignment_meta = assignment_meta['Items'][0]
                assert_that(assignment_meta['AssignmentTitle'], is_(assignment.title))
                assert_that(assignment_meta['AssignmentNTIID'], is_(assignment.ntiid))
                assert_that(assignment_meta['CompletionDate'], not_none())
                assert_that(assignment_meta['Success'], is_(success))
                assert_that(assignment_meta['CompletionRequiredPassingPercentage'], is_(passing_percentage))
                assert_that(assignment_meta['UserPointsReceived'], is_(10.0))
                assert_that(assignment_meta['TotalPoints'], is_(20))

        def validate_incompletion():
            validate_completion(progress=False, complete=False)

        validate_incompletion()

        # Grades/excused
        instructor_environ = self._make_extra_environ(username='harp4162')
        # Course completion on, require assignment
        policy_res = self._set_completion_policy(instructor_environ)
        required_url = self.require_link_href_with_rel(policy_res,
                                                       COMPLETION_REQUIRED_VIEW_NAME)
        self.testapp.put_json(required_url, {u'ntiid': assignment_id},
                              extra_environ=instructor_environ)
        grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/SetGrade'
        trivial_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial Test/'
        path = trivial_grade_path + 'sjohnson@nextthought.com'
        excuse_path = '%s/excuse' % path
        unexcuse_path = '%s/unexcuse' % path
        grade = {'Username': 'sjohnson@nextthought.com',
                 'AssignmentId': assignment_id,
                 'value': 10}
        grade2 = dict(grade)
        grade2['value'] = 100
        grade3 = dict(grade)
        grade3['value'] = 10
        self.testapp.post_json(grade_path, grade, extra_environ=instructor_environ)
        self.testapp.post_json(grade_path, grade2, extra_environ=instructor_environ)
        grade_res = self.testapp.post_json(grade_path, grade3, extra_environ=instructor_environ)
        grade_res = grade_res.json_body
        # Validate we only have a single placeholder item
        assert_that(grade_res['Items'], has_length(1))
        reset_rel = self.require_link_href_with_rel(grade_res, 'Reset')

        # Grade without submission is incomplete
        validate_incompletion()

        # Excusing does so
        self.testapp.post(excuse_path, extra_environ=instructor_environ)
        validate_completion()

        # Unexcusing reverts
        self.testapp.post(unexcuse_path, extra_environ=instructor_environ)
        validate_incompletion()

        # Now reset
        self.testapp.post(reset_rel, extra_environ=instructor_environ)
        validate_incompletion()

        # Submitting is complete
        submit_href = '/dataserver2/Objects/%s?ntiid=%s' % (assignment_id, COURSE_NTIID)

        # Get one correct and one incorrect
        qs1_submission = QuestionSetSubmission(questionSetId=qs_id1,
                                               questions=(QuestionSubmission(questionId=question_id1, parts=[0]),))
        # The incorrect one is partially correct on parts, but the whole thing
        # is still graded wrong
        qs2_submission = QuestionSetSubmission(questionSetId=qs_id2,
                                               questions=(QuestionSubmission(questionId=question_id2, parts=[0, 1]),))

        submission = AssignmentSubmission(assignmentId=assignment_id,
                                          parts=(qs1_submission, qs2_submission))

        ext_obj = to_external_object(submission)
        del ext_obj['Class']
        assert_that(ext_obj,
                    has_entry('MimeType', 'application/vnd.nextthought.assessment.assignmentsubmission'))
        # Make sure we're enrolled
        enroll_record = self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                                               COURSE_NTIID)
        enroll_record = enroll_record.json_body
        enroll_record_href = enroll_record['href']
        # Make sure we have no notable items
        notable_res = self.fetch_user_recursive_notable_ugd()
        assert_that(notable_res.json_body, has_entry('TotalItemCount', 0))

        assignment_res = self.testapp.get(submit_href)
        start_href = self.require_link_href_with_rel(assignment_res.json_body,
                                                     'Commence')
        self.testapp.post(start_href)
        res = self.testapp.post_json(submit_href, ext_obj, status=201)
        history_path = self.require_link_href_with_rel(res.json_body, 'AssignmentHistoryItem')
        history_res = self.testapp.get(history_path)
        # We were half right
        assert_that(history_res.json_body,
                    has_entry('Grade', has_entries('value', 10.0,
                                                   'AutoGrade', 10.0,
                                                   'AutoGradeMax', 20.0)))

        # Because it auto-grades, we have a notable item
        notable_res = self.fetch_user_recursive_notable_ugd()
        assert_that(notable_res.json_body, has_entry('TotalItemCount', 1))
        assert_that(notable_res.json_body['Items'][0]['Item'],
                    has_entry('Creator', 'system'))

        validate_completion()

        with mock_dataserver.mock_db_trans(self.ds):
            course = find_object_with_ntiid(COURSE_NTIID)
            course = ICourseInstance(course)
            assignment = find_object_with_ntiid(assignment_id)
            user = User.get_user('sjohnson@nextthought.com')
            progress = component.queryMultiAdapter((user, assignment, course),
                                                   IProgress)
            assert_that(progress, not_none())
            assert_that(progress.AbsoluteProgress, is_(10.0))
            assert_that(progress.MaxPossibleProgress, is_(20))
            assert_that(progress.LastModified, not_none())
            assert_that(progress.HasProgress, is_(True))

            principal_container = component.queryMultiAdapter((user, course),
                                                              IPrincipalCompletedItemContainer)
            assert_that(principal_container, not_none())
            assert_that(principal_container, has_length(1))
            assert_that(principal_container.get_completed_item_count(), is_(1))
            completed_item = principal_container.get_completed_item(assignment)
            assert_that(completed_item, not_none())
            assert_that(completed_item.Item, is_(assignment))
            assert_that(completed_item.Principal.id, is_(user.username))
            assert_that(completed_item.CompletedDate, not_none())

        # Validate required perc (user gets 10/20 pts)
        update_passing_perc(.6)
        self.testapp.post(reset_rel, extra_environ=instructor_environ)
        self.testapp.post(start_href)
        self.testapp.post_json(submit_href, ext_obj)
        validate_completion(success=False, enroll_record_href=enroll_record_href, passing_percentage=.6)

        update_passing_perc(.01)
        self.testapp.post(reset_rel, extra_environ=instructor_environ)
        self.testapp.post(start_href)
        self.testapp.post_json(submit_href, ext_obj)
        validate_completion(success=True, enroll_record_href=enroll_record_href, passing_percentage=.01)

        update_passing_perc(.5)
        self.testapp.post(reset_rel, extra_environ=instructor_environ)
        self.testapp.post(start_href)
        self.testapp.post_json(submit_href, ext_obj)
        validate_completion(success=True, enroll_record_href=enroll_record_href, passing_percentage=.5)

        update_passing_perc(1.0)
        self.testapp.post(reset_rel, extra_environ=instructor_environ)
        self.testapp.post(start_href)
        self.testapp.post_json(submit_href, ext_obj)
        validate_completion(success=False, enroll_record_href=enroll_record_href, passing_percentage=1.0)

        # Without total_points, we should have an incomplete state (no
        # completion state). This is what should occur for non auto-graded
        # assignments with a required passing percent.
        mock_auto_grade.is_callable().returns(None)
        mock_auto_grade2.is_callable().returns(None)
        self.testapp.post(reset_rel, extra_environ=instructor_environ)
        self.testapp.post(start_href)
        self.testapp.post_json(submit_href, ext_obj)
        validate_completion(progress=True, complete=False, enroll_record_href=enroll_record_href)

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_instructor_grade_is_ugd_notable_to_student(self):
        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        instructor_environ = self._make_extra_environ(username='harp4162')

        # If the instructor puts in a grade...
        trivial_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial Test/'
        path = trivial_grade_path + 'sjohnson@nextthought.com'
        grade = {'Class': 'Grade'}
        grade['value'] = 10
        res = self.testapp.put_json(path, grade, extra_environ=instructor_environ)
        history_path = self.require_link_href_with_rel(res.json_body, 'AssignmentHistoryItem')

        # It shows up as a notable item for the student
        notable_res = self.fetch_user_recursive_notable_ugd()
        assert_that(notable_res.json_body, has_entry('TotalItemCount', 1))

        # If the instructor deletes it...
        # (delete indirectly by resetting the submission to be sure the right
        # event chain works)
        #history_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses/%s/AssignmentHistories/sjohnson@nextthought.com/UserCourseAssignmentHistoryItem' % COURSE_NTIID
        history_res = self.testapp.get(history_path)
        submission = history_res.json_body

        #submission = history_res.json_body['Items']['tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.trivial_test']
        self.testapp.delete(submission['href'],
                            extra_environ=instructor_environ)

        # The notable item is gone
        notable_res = self.fetch_user_recursive_notable_ugd()
        assert_that(notable_res.json_body, has_entry('TotalItemCount', 0))

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    @time_monotonically_increases
    def test_mutating_grade_changes_history_item_last_modified(self):
        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        instructor_environ = self._make_extra_environ(username='harp4162')

        # If the instructor puts in a grade...
        trivial_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial Test/'
        path = trivial_grade_path + 'sjohnson@nextthought.com'
        grade = {'Class': 'Grade'}
        grade['value'] = 10
        res = self.testapp.put_json(path, grade, extra_environ=instructor_environ)
        history_path = self.require_link_href_with_rel(res.json_body, 'AssignmentHistoryItem')

        # ...the student sees a history item
        history_res = self.testapp.get(history_path)
        history_item = history_res.json_body

        history_lm = history_item['Last Modified']
        history_item['Grade']['value']

        # If the instructor updates it
        grade['value'] = 5
        self.testapp.put_json(path, grade, extra_environ=instructor_environ)

        history_res = self.testapp.get(history_path)
        history_item2 = history_res.json_body
        #history_item2 = history_res.json_body['Items']['tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg.trivial_test']

        history_item['Last Modified']
        history_item['Grade']['value']

        # The date and data are modified
        assert_that(history_item2, has_entries('Last Modified', greater_than(history_lm),
                                               'Grade', has_entry('value', 5)))

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_instructor_delete_grade(self):
        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        instructor_environ = self._make_extra_environ(username='harp4162')

        # If the instructor puts in a grade...
        trivial_grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial Test/'
        path = trivial_grade_path + 'sjohnson@nextthought.com'
        grade = {'Class': 'Grade'}
        grade['value'] = 10
        grade_res = self.testapp.put_json(path, grade,
                                          extra_environ=instructor_environ)

        # he can later delete it
        self.testapp.delete(grade_res.json_body['href'],
                            extra_environ=instructor_environ)

        # the user has no notable item for it
        notable_res = self.fetch_user_recursive_notable_ugd()
        assert_that(notable_res.json_body, has_entry('TotalItemCount', 0))

        # deleting the same (or any missing) grade raises
        # a 404
        self.testapp.delete(grade_res.json_body['href'],
                            status=404,
                            extra_environ=instructor_environ)

        # The prof can put the grade back again
        self.testapp.put_json(path, grade, extra_environ=instructor_environ)

        # and delete again
        self.testapp.delete(grade_res.json_body['href'],
                            extra_environ=instructor_environ)

    @WithSharedApplicationMockDS(users=('regular_user',), testapp=True, default_authenticate=True)
    def test_gradebook_rel_presence(self):
        # Make sure we're enrolled
        normal_environ = self._make_extra_environ(username='regular_user')

        res = self.testapp.post_json('/dataserver2/users/regular_user/Courses/EnrolledCourses',
                                     COURSE_NTIID,
                                     status=201,
                                     extra_environ=normal_environ)
        course_rel = self.require_link_href_with_rel(res.json_body, 'CourseInstance')
        course_res = self.testapp.get(course_rel, extra_environ=normal_environ).json_body
        course_instance_href = course_res['href']

        res = self.testapp.get(course_instance_href,
                               extra_environ=normal_environ)

        self.forbid_link_with_rel(res.json_body, 'GradeBook')

        instructor_environ = self._make_extra_environ(username='harp4162')

        res = self.testapp.get(course_instance_href,
                               extra_environ=instructor_environ)

        gb_href = self.require_link_href_with_rel(res.json_body, 'GradeBook')

        self.testapp.get(gb_href, extra_environ=instructor_environ)

        self.testapp.get(gb_href, extra_environ=normal_environ, status=403)
