#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import not_
from hamcrest import has_entry
from hamcrest import has_key
from hamcrest import has_length
from hamcrest import assert_that

import fudge

from nti.app.testing.decorators import WithSharedApplicationMockDS

from nti.app.products.gradebook.views.grading_views import is_none

from nti.app.products.gradebook.tests import InstructedCourseApplicationTestLayer

from nti.app.testing.application_webtest import ApplicationLayerTest

COURSE_NTIID = 'tag:nextthought.com,2011-10:OU-HTML-CLC3403_LawAndJustice.course_info'


class TestViews(ApplicationLayerTest):

    default_origin = str('http://janux.ou.edu')

    layer = InstructedCourseApplicationTestLayer

    gradebook_part = {'Name': 'Quizzes', 'order': 1,
                      'MimeType': 'application/vnd.nextthought.gradebookpart'}

    gradebook_entry = {'Name': 'Quiz1', 'order': 2,
                       'AssignmentId': 'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403',
                       'MimeType': 'application/vnd.nextthought.gradebookentry'}

    grade = {'username': 'sjohnson@nextthought.com', 'grade': 85, 'NTIID': None,
             'MimeType': 'application/vnd.nextthought.grade'}

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_gradebook_delete(self):
        environ = self._make_extra_environ()
        environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'

        res = self.testapp.get(
            '/dataserver2/users/sjohnson@nextthought.com/Courses/AllCourses', extra_environ=environ)
        href = self.require_link_href_with_rel(
            res.json_body['Items'][0], 'CourseInstance')

        gradebook_href = path = href + '/GradeBook'

        res = self.testapp.get(path, extra_environ=environ)
        assert_that(res.json_body, has_entry(
            'NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403'))
        assert_that(res.json_body, has_entry('Items', has_length(3)))

        # As an admin, we can delete it...it will be reset on startup
        self.testapp.delete(gradebook_href, extra_environ=environ)
        res = self.testapp.get(path, extra_environ=environ)
        assert_that(res.json_body, has_entry(
            'NTIID', u'tag:nextthought.com,2011-10:NextThought-gradebook-CLC3403'))
        assert_that(res.json_body, has_entry('Items', has_length(0)))

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_grade_excuse_views(self):

        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        environ = self._make_extra_environ()
        environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
        instructor_environ = self._make_extra_environ(username='harp4162')
        path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial%20Test/'

        # We don't have a grade yet, so this returns a placeholder grade
        # without a value.
        res = self.testapp.get(
            path + 'sjohnson@nextthought.com/', extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('value', None))

        # We don't have a grade submission yet, but we should still
        # be able to excuse the grade. A placeholder grade gets created
        # and excused, and we can verify the returned object is excused.
        # The value is still None.
        self.testapp.post(
            path + 'sjohnson@nextthought.com/excuse', extra_environ=instructor_environ)
        res = self.testapp.get(
            path + 'sjohnson@nextthought.com', extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('IsExcused', True))
        assert_that(res.json_body, has_entry('value', None))

        # We can also unexcuse this placeholder grade.
        self.testapp.post(
            path + 'sjohnson@nextthought.com/unexcuse', extra_environ=instructor_environ)
        res = self.testapp.get(
            path + 'sjohnson@nextthought.com', extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('IsExcused', False))
        assert_that(res.json_body, has_entry('value', None))

        # A non-instructor should not be able to excuse or unexcuse a grade.
        res = self.testapp.post(
            path + 'sjohnson@nextthought.com/excuse', extra_environ=environ, status=403)
        res = self.testapp.post(
            path + 'sjohnson@nextthought.com/unexcuse', extra_environ=environ, status=403)

        # Even though we have a placeholder grade in place, we should be able to
        # set its value normally if we assign a grade.
        grade_path = path + 'sjohnson@nextthought.com'
        grade = {'Class': 'Grade'}
        grade['value'] = 10
        self.testapp.put_json(
            grade_path, grade, extra_environ=instructor_environ)
        res = self.testapp.get(
            path + 'sjohnson@nextthought.com', extra_environ=instructor_environ)
        assert_that(res.json_body, has_entry('IsExcused', False))
        assert_that(res.json_body, has_entry('value', 10))

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    @fudge.patch('nti.app.products.gradebook.grading.policies.simple.SimpleTotalingGradingPolicy._get_total_points_for_assignment')
    def test_current_grade_view(self, mock_total_points):

        mock_total_points.is_callable().with_args().returns(15)

        # Make sure we're enrolled
        self.testapp.post_json('/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses',
                               COURSE_NTIID,
                               status=201)

        environ = self._make_extra_environ()
        environ[b'HTTP_ORIGIN'] = b'http://platform.ou.edu'
        instructor_environ = self._make_extra_environ(username='harp4162')

        policy = {"Class": "SimpleTotalGradingPolicy",
                  "MimeType": "application/vnd.nextthought.gradebook.simpletotalinggradingpolicy"}
        course_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403'
        policy_view_path = course_path + '/GradingPolicy'
        current_grade_path = course_path + '/CurrentGrade'

        # We can't get CurrentGrade if the course does not
        # define a grading policy.
        self.testapp.get(current_grade_path, status=422)
        # Add the simple grading policy to use for the rest of this test.
        self.testapp.post_json(
            policy_view_path, policy, extra_environ=instructor_environ, status=201)

        # Should 404 if we have no grades yet.
        self.testapp.get(current_grade_path, status=404)

        # Should get a dict back with 'PredictedGrade'
        # if we have one.
        grade_entry_path = course_path + \
            '/GradeBook/quizzes/Trivial%20Test/sjohnson@nextthought.com'
        grade = {'Class': 'Grade',
                 'value': 10}
        res = self.testapp.put_json(
            grade_entry_path, grade, extra_environ=instructor_environ)
        # (save this NTIID to use later when we delete it)
        predicted_grade_ntiid = res.json_body['NTIID']

        res = self.testapp.get(current_grade_path)
        assert_that(res.json_body, has_key('PredictedGrade'))
        assert_that(
            res.json_body['PredictedGrade'], has_entry('PointsEarned', 10))
        assert_that(res.json_body, not_(has_key('FinalGrade')))

        # Should get a dict back with both 'PredictedGrade'
        # and 'FinalGrade' if we have both.
        grade = {'Class': 'Grade',
                 'value': 75}
        final_grade_path = course_path + \
            '/GradeBook/no_submit/Final Grade/sjohnson@nextthought.com'
        self.testapp.put_json(
            final_grade_path, grade, extra_environ=instructor_environ)
        res = self.testapp.get(current_grade_path)
        assert_that(res.json_body, has_key('PredictedGrade'))
        assert_that(
            res.json_body['PredictedGrade'], has_entry('PointsEarned', 10))
        assert_that(res.json_body, has_key('FinalGrade'))

        # If we delete the PredictedGrade and then call
        # CurrentGrade again, we should get just a FinalGrade
        # back in the dictionary.
        self.testapp.delete(grade_entry_path, extra_environ=instructor_environ)
        res = self.testapp.get(current_grade_path)
        assert_that(res.json_body, has_key('FinalGrade'))
        assert_that(res.json_body, not_(has_key('PredictedGrade')))

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_download_gradebook_view(self):
        instructor_environ = self._make_extra_environ(username='harp4162')
        
        path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/contents.csv'
        
        grade_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradeBook/quizzes/Trivial%20Test/sjohnson@nextthought.com'
        
        enroll_path = '/dataserver2/users/sjohnson@nextthought.com/Courses/EnrolledCourses'
        
        self.testapp.post_json(enroll_path,
                          COURSE_NTIID,
                          extra_environ=self._make_extra_environ())
        
        grade = {'Class': 'Grade'}
        grade['value'] = 10
        self.testapp.put_json(
            grade_path, grade, extra_environ=instructor_environ)
        
        res = self.testapp.get(path,
                               extra_environ=instructor_environ)

    @WithSharedApplicationMockDS(users=True, testapp=True, default_authenticate=True)
    def test_policy_views(self):

        instructor_environ = self._make_extra_environ(username='harp4162')

        policy = {"Class": "SimpleTotalGradingPolicy",
                  "MimeType": "application/vnd.nextthought.gradebook.simpletotalinggradingpolicy"}
        policy_view_path = '/dataserver2/users/CLC3403.ou.nextthought.com/LegacyCourses/CLC3403/GradingPolicy'

        # No grading policy by default, so it should 404
        res = self.testapp.get(policy_view_path, status=404)

        # A non-instructor should not be able to set the policy
        res = self.testapp.post_json(
            policy_view_path, policy, status=403)

        # Adding the policy correctly should work
        self.testapp.post_json(
            policy_view_path, policy, extra_environ=instructor_environ, status=201)
        res = self.testapp.get(policy_view_path)
        assert_that(
            res.json_body, has_entry('Class', 'SimpleTotalingGradingPolicy'))

        # Deleting the policy
        self.testapp.delete(
            policy_view_path, extra_environ=instructor_environ)
        res = self.testapp.get(policy_view_path, status=404)

    def test_is_none(self):
        assert_that(is_none(None), is_(True))
        assert_that(is_none(''), is_(True))
        assert_that(is_none('-'), is_(True))
        assert_that(is_none(' - '), is_(True))

        assert_that(is_none(5), is_(False))
        assert_that(is_none('--'), is_(False))
        assert_that(is_none('D - '), is_(False))
        assert_that(is_none('55 D-'), is_(False))
