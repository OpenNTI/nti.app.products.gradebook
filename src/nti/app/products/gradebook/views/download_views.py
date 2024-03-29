#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division

logger = __import__('logging').getLogger(__name__)

import csv
import six
import nameparser
from six import StringIO
from collections import defaultdict

from zope import component

from zope.cachedescriptors.property import Lazy

from pyramid.view import view_config

from nti.app.assessment.common.policy import get_policy_excluded

from nti.app.assessment.common.utils import get_available_for_submission_beginning

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IExcusedGrade
from nti.app.products.gradebook.interfaces import FINAL_GRADE_NAMES
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.base.interfaces import DEFAULT_CONTENT_TYPE

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IProfileDisplayableSupplementalFields

from nti.dataserver.users.users import User

from nti.externalization.interfaces import LocatedExternalList

from nti.mailer.interfaces import IEmailAddressable

from nti.namedfile.file import safe_filename

from nti.ntiids.ntiids import find_object_with_ntiid


def get_valid_assignment(entry, course):
    """
    We only want entries that point to assignments that exist and are not
    excluded.
    """
    assignment = find_object_with_ntiid(entry.AssignmentId)
    if      assignment is not None \
        and get_policy_excluded(assignment, course):
            return None
    return assignment


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             context=IGradeBook,
             permission=nauth.ACT_READ,
             name='contents.csv')
class GradebookDownloadView(AbstractAuthenticatedView):
    """
    Provides a downloadable table of all the assignments
    present in the gradebook. There is a column
    for each assignment and a row for each user.

    A query param `LegacyEnrollmentStatus` can be set to
    either 'ForCredit' or 'Open' to restrict the results to that
    subset of students.
    """

    @property
    def _enrollment_filter(self):
        return self.request.GET.get('LegacyEnrollmentStatus')

    def _make_enrollment_predicate(self):
        status_filter = self._enrollment_filter
        if not status_filter:
            return lambda unused_course, unused_user: True

        def f(course, user):
            # TODO: Replace this with
            # nti.contenttypes.courses.interfaces.ICourseInstanceEnrollmentRecord
            enrollment = component.queryMultiAdapter((course, user),
                                                     ICourseInstanceEnrollment)
            if enrollment is None:
                # We have a submitted assignment for a user no longer enrolled.
                return False
            # Let this blow up when this goes away
            return enrollment.LegacyEnrollmentStatus == status_filter
        return f

    def _string(self, val):
        return val.replace(' ', '') if val else val

    def _get_course_name(self, course):
        entry = ICourseCatalogEntry(course, None)
        if entry is not None:
            base_name = entry.ProviderUniqueID
            base_name = self._string(base_name)
        if not base_name:
            base_name = course.__name__
        return base_name

    def _get_filename(self, course):
        suffix = 'grades.csv'
        base_name = self._get_course_name(course)
        filter_name = self._enrollment_filter
        filter_name = self._string(filter_name) or 'full'
        result = '%s_%s-%s' % (base_name, filter_name, suffix)
        return result

    def _get_user_info_dict(self, username):
        user = User.get_user(username)
        firstname = lastname = realname = ''
        if user is not None:
            named_user = IUserProfile(user)
            realname = named_user.realname
            if named_user.realname and '@' not in named_user.realname:
                human_name = nameparser.HumanName(named_user.realname)
                lastname = human_name.last or ''
                firstname = human_name.first or ''
        result = {'firstName': firstname,
                  'lastName': lastname,
                  'username': username,
                  'realname': realname}
        if user is not None and self.supplemental_field_utility:
            result.update(self.supplemental_field_utility.get_user_fields(user))
        return result

    def _get_entry_start_date(self, entry, course):
        assignment = find_object_with_ntiid(entry.AssignmentId)
        if assignment is not None:
            return get_available_for_submission_beginning(assignment, context=course)
        logger.warn('Assignment %s does not exist', assignment)
        return None

    def _get_sort_key(self, entry, course):
        """
        Sort gradebook entry by StartDate and display name.
        """
        start_date = self._get_entry_start_date(entry, course)
        entry_name = entry.displayName or 'Unknown'
        return (start_date is not None, start_date, entry_name)

    @Lazy
    def supplemental_field_utility(self):
        return component.queryUtility(IProfileDisplayableSupplementalFields)

    @Lazy
    def _supplemental_ordered_fields(self):
        return self.supplemental_field_utility \
           and self.supplemental_field_utility.get_ordered_fields()

    def _get_supplemental_header(self):
        result = []
        if self.supplemental_field_utility:
            display_dict = self.supplemental_field_utility.get_field_display_values()
            supp_fields = self.supplemental_field_utility.get_ordered_fields()
            for supp_field in supp_fields:
                result.append(display_dict.get(supp_field))
        return result

    def _get_supplemental_data(self, user_info_dict):
        data = []
        if self.supplemental_field_utility:
            for supp_field in self._supplemental_ordered_fields:
                data.append(user_info_dict.get(supp_field, ''))
        return data

    def __call__(self):
        gradebook = self.request.context
        course = ICourseInstance(gradebook)
        predicate = self._make_enrollment_predicate()

        # We build a dictionary of {user_data: {Assignment: Grade} }, where
        # user_data contains first and last names, the username, and the realname.
        # (This is to avoid parsing names more often than we need to.)
        # We keep track of known assignment names so we can sort appropriately;
        # it is keyed by the column name (as that's the only thing guaranteed
        # to be unique) and the value is a sortable key.
        usernames_to_assignment_dict = defaultdict(dict)
        user_info_dicts = {}
        # (assignment_ntiid, assignment_title) -> data
        seen_assignment_keys_to_start_time = dict()
        final_grade_entry = None

        for part in gradebook.values():
            for name, entry in part.items():
                if	    part.__name__ == NO_SUBMIT_PART_NAME \
                    and name in FINAL_GRADE_NAMES:
                    final_grade_entry = entry
                    continue
                assignment = get_valid_assignment(entry, course)
                if assignment is None:
                    continue
                # We always want our assignment display name
                assignment_key = (assignment.ntiid, assignment.title)
                sort_key = self._get_sort_key(entry, course)
                seen_assignment_keys_to_start_time[assignment_key] = sort_key
                for username, grade in entry.items():
                    if username not in user_info_dicts:
                        user_info_dicts[username] = self._get_user_info_dict(username)
                    user_dict = usernames_to_assignment_dict[username]
                    # This should not be possible anymore
                    if assignment_key in user_dict:
                        raise ValueError("Two entries in different part with same name")
                    user_dict[assignment_key] = grade

        sorted_assignment_keys = sorted(seen_assignment_keys_to_start_time,
                                        key=seen_assignment_keys_to_start_time.get)

        # Now we can build up the rows.
        rows = LocatedExternalList()
        rows.__name__ = self.request.view_name
        rows.__parent__ = self.request.context

        def _tx_string(val):
            # At least in python 2, the CSV writer only works correctly with
            # str objects, implicitly encoding otherwise.
            if isinstance(val, six.text_type):
                val = val.encode('utf-8')
            return val

        # First a header row. Note that we are allowed to use multiple columns
        # to identify students.
        headers = ['Username', 'First Name', 'Last Name', 'Full Name', 'Email']
        headers.extend(self._get_supplemental_header())
        # Assignment names could theoretically have non-ascii chars
        for asg_tuple in sorted_assignment_keys:
            asg_name = _tx_string(asg_tuple[1])
            # Avoid unicode conversion of our already encoded str.
            asg_name = asg_name + str(' Points Grade')
            headers.append(asg_name)
        headers.extend(['Adjusted Final Grade Numerator',
                        'Adjusted Final Grade Denominator',
                        'End-of-Line Indicator'])
        rows.append(headers)

        # Now a row for each user and each assignment in the same order.
        # Note that the webapp tends to send string values even when the user
        # typed a number: "75 -". For export purposes, if we can reverse that to a number,
        # we want it to be a number.
        def _tx_grade(value):
            if not isinstance(value, six.string_types):
                return value
            if value.endswith(' -'):
                try:
                    return int(value[:-2])
                except ValueError:
                    try:
                        return float(value[:-2])
                    except ValueError:
                        return _tx_string(value)

        # Sort by last name, then first name, then username
        for username, user_info_dict in sorted(user_info_dicts.items(),
                                               key=lambda kv: (kv[1].get('lastName'),
                                                               kv[1].get('firstName'),
                                                               kv[1].get('username'))):
            user = User.get_user(username)
            if not user or not predicate(course, user):
                continue
            firstname = user_info_dict.get('firstName')
            lastname = user_info_dict.get('lastName')
            realname = user_info_dict.get('realname')
            email_addressable = IEmailAddressable(user, None)
            email = email_addressable.email if email_addressable else None

            data = [username, firstname, lastname, realname, email]
            data.extend(self._get_supplemental_data(user_info_dict))
            row = [_tx_string(x) for x in data]

            user_data_dict = usernames_to_assignment_dict.get(username)
            for assignment_key in sorted_assignment_keys:
                grade_val = ""
                if assignment_key in user_data_dict:
                    user_grade = user_data_dict[assignment_key]
                    grade_val = user_grade.value
                    # For CS1323, we need to expose Excused grades. It's not entirely clear
                    # how to do so in a D2L import-compatible way, but we've seen text
                    # exported values (from our system) anyway, which are probably not
                    # imported into D2L.
                    if IExcusedGrade.providedBy(user_grade):
                        grade_val = _(u'Excused')
                    else:
                        grade_val = _tx_grade(grade_val)
                row.append(grade_val)

            if final_grade_entry:
                final_grade = final_grade_entry.get(username)
            else:
                final_grade = None
            row.append(_tx_grade(final_grade.value) if final_grade else 0)
            row.append(100)

            # End-of-line
            row.append('#')
            rows.append(row)

        # Anyone enrolled but not submitted gets a blank row
        # at the bottom...except that breaks the D2L model

        # Convert to CSV
        # In the future, we might switch based on the accept header
        # and provide it as json or XLS alternately
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerows(rows)

        filename = self._get_filename(course)
        content_disposition = 'attachment; filename="%s"' % safe_filename(filename)
        self.request.response.body = buf.getvalue()
        self.request.response.content_disposition = content_disposition
        self.request.response.content_type = DEFAULT_CONTENT_TYPE
        return self.request.response
