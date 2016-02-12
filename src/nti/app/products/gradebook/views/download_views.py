#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import csv
import six
import nameparser
import collections
from cStringIO import StringIO

from zope import component

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IExcusedGrade
from nti.app.products.gradebook.interfaces import NO_SUBMIT_PART_NAME

from nti.app.products.gradebook.utils import replace_username

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.interfaces import LocatedExternalList

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

	.. note:: This is hardcoded to export in D2L compatible format.
		(https://php.radford.edu/~knowledge/lore/attachment.php?id=57)
		Dialects would be easily possible.
	"""
	@property
	def _enrollment_filter(self):
		return self.request.GET.get('LegacyEnrollmentStatus')

	def _make_enrollment_predicate(self):
		status_filter = self._enrollment_filter
		if not status_filter:
			return lambda course, user: True

		def f(course, user):
			# TODO: Replace this with nti.contenttypes.courses.interfaces.ICourseInstanceEnrollmentRecord
			enrollment = component.queryMultiAdapter((course, user),
													 ICourseInstanceEnrollment)
			if enrollment is None:
				# We have a submitted assignment for a user no longer enrolled.
				return False
			return enrollment.LegacyEnrollmentStatus == status_filter  # Let this blow up when this goes away
		return f

	def _string(self, val):
		if val:
			val = val.replace(' ', '')
		return val

	def _get_course_name(self, course):
		entry = ICourseCatalogEntry(course, None)
		if entry is not None:
			base_name = entry.ProviderUniqueID
			base_name = self._string(base_name)
		if not base_name:
			base_name = course.__name__
		return base_name

	def _get_filename(self, course):
		base_name = self._get_course_name(course)
		filter_name = self._enrollment_filter
		filter_name = self._string(filter_name) or 'full'
		suffix = 'grades.csv'
		result = '%s_%s-%s' % (base_name, filter_name, suffix)
		return result

	def __call__(self):
		gradebook = self.request.context
		course = ICourseInstance(gradebook)
		predicate = self._make_enrollment_predicate()

		# We build a dictionary of {username: {Assignment: Grade} }
		# We keep track of known assignment names so we can sort appropriately;
		# it is keyed by the column name (as that's the only thing guaranteed
		# to be unique) and the value is the display name
		usernames_to_assignment_dict = collections.defaultdict(dict)
		seen_asg_names = dict()

		final_grade_entry = None

		for part in gradebook.values():
			for name, entry in part.items():
				if part.__name__ == NO_SUBMIT_PART_NAME and name == 'Final Grade':
					final_grade_entry = entry
					continue

				seen_asg_names[name] = entry.displayName or 'Unknown'
				for username, grade in entry.items():
					user_dict = usernames_to_assignment_dict[username]
					if name in user_dict:
						raise ValueError("Two entries in different part with same name")
					user_dict[name] = grade

		# Now, sort the *display* names, maintaining the
		# association to the actual part name
		sorted_asg_names = sorted((v, k) for k, v in seen_asg_names.items())

		# Now we can build up the rows.
		rows = LocatedExternalList()
		rows.__name__ = self.request.view_name
		rows.__parent__ = self.request.context

		def _tx_string(val):
			# At least in python 2, the CSV writer only works
			# correctly with str objects, implicitly encoding
			# otherwise
			if isinstance(val, unicode):
				val = val.encode('utf-8')
			return val

		# First a header row. Note that we are allowed to use multiple columns to
		# identify students.
		headers = ['Username', 'External ID', 'First Name', 'Last Name', 'Full Name']
		# Assignment names could theoretically have non-ascii chars
		for asg in sorted_asg_names:
			asg_name = _tx_string(asg[0])
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

		for username, user_dict in sorted(usernames_to_assignment_dict.items()):
			user = User.get_user(username)
			if not user or not predicate(course, user):
				continue

			profile = IUserProfile(user)
			external_id = replace_username(username)

			realname = profile.realname or ''
			if realname and '@' not in realname and realname != username:
				human_name = nameparser.HumanName(realname)
				firstname = human_name.first or ''
				lastname = human_name.last or ''
			else:
				firstname = ''
				lastname = ''

			data = (username, external_id, firstname, lastname, realname)
			row = [_tx_string(x) for x in data]
			for _, assignment in sorted_asg_names:
				grade_val = ""
				if assignment in user_dict:
					user_grade = user_dict[assignment]
					grade_val = user_grade.value
					# For CS1323, we need to expose Excused grades. It's not entirely clear
					# how to do so in a D2L import-compatible way, but we've seen text
					# exported values (from our system) anyway, which are probably not
					# imported into D2L.
					grade_val = 'Excused' if IExcusedGrade.providedBy(user_grade) else _tx_grade(grade_val)
				row.append(grade_val)

			final_grade = final_grade_entry.get(username) if final_grade_entry else None
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
		content_disposition = str('attachment; filename="%s"' % filename)
		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = content_disposition
		self.request.response.content_type = str('application/octet-stream')
		return self.request.response
