#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grades definition

.. $Id$
"""

from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.mimetype.interfaces import IContentTypeAware

from persistent import Persistent

from nti.app.products.gradebook.interfaces import IGrade

from nti.contenttypes.courses.grading.interfaces import IPredictedGrade

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_denying_all

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import ICreated

from nti.dublincore.datastructures import CreatedModDateTrackingObject

from nti.externalization.representation import WithRepr

from nti.property.property import Lazy
from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from nti.wref.interfaces import IWeakRef

from nti.zodb.persistentproperty import PersistentPropertyHolder


@WithRepr
@interface.implementer(IGrade)
@EqHash('username', 'assignmentId', 'value')
class Grade(CreatedModDateTrackingObject,
            SchemaConfigured,
            Contained):

    createDirectFieldProperties(IGrade)

    grade = alias('value')
    username = alias('Username')
    Username = alias('__name__')
    assignmentId = alias('AssignmentId')

    # Right now, we inherit the 'creator' property
    # from CreatedModDateTrackingObject, but we have no real
    # need for it (also, some extent objects in the database
    # don't have a value for it), so provide a default that
    # ignores it
    creator = None

    def __init__(self, *args, **kwargs):
        if 'grade' in kwargs and 'value' not in kwargs:
            kwargs['value'] = kwargs['grade']
            del kwargs['grade']
        if 'username' in kwargs and 'Username' not in kwargs:
            kwargs['Username'] = kwargs['username']
            del kwargs['username']
        super(Grade, self).__init__(**kwargs)

    @Lazy
    def createdTime(self):
        # Some old objects in the database won't have a value for
        # created time; in that case, default to lastModified.
        # Some old objects in the database will have a lastModified
        # of 0, though, nothing we can do about that...
        return self.lastModified

    @property
    def AssignmentId(self):
        if self.__parent__ is not None:
            return self.__parent__.AssignmentId

    # Since we're not persistent, the regular use of CachedProperty fails
    @property
    def __acl__(self):
        acl = acl_from_aces()
        course = ICourseInstance(self, None)
        if course is not None:
            acl.extend((ace_allowing(i, ALL_PERMISSIONS)
                        for i in course.instructors))
        # This will become conditional on whether we are published
        if self.Username:
            acl.append(ace_allowing(self.Username, ACT_READ))
        acl.append(ace_denying_all())
        return acl


@interface.implementer(IWeakRef)
@component.adapter(IGrade)
class GradeWeakRef(object):
    """
    A weak reference to a grade. Because grades are non-persistent,
    we reference them by name inside of a part of a gradebook.
    This means that we can resolve to different object instances
    even during the same transaction, although they are logically the same
    grade.
    """

    __slots__ = ('_part_wref', '_username')

    def __init__(self, grade):
        if grade.__parent__ is None or not grade.Username:
            raise TypeError("Too soon, grade has no parent or username")

        self._username = grade.Username
        self._part_wref = IWeakRef(grade.__parent__)

    def __call__(self):
        part = self._part_wref()
        if part is not None:
            return part.get(self._username)

    def __eq__(self, other):
        try:
            return  self is other or \
                    (self._username, self._part_wref) == (other._username, other._part_wref)
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash((self._username, self._part_wref))

    def __getstate__(self):
        return self._part_wref, self._username

    def __setstate__(self, state):
        self._part_wref, self._username = state


@interface.implementer(ICreated, IContentTypeAware)
class PersistentGrade(Grade, PersistentPropertyHolder):
    # order of inheritance matters; if Persistent is first,
    # we can't have our own __setstate__; only subclasses can

    __external_class_name__ = "Grade"

    parameters = {}
    mimeType = mime_type = 'application/vnd.nextthought.grade'

    def __init__(self, *args, **kwargs):
        Grade.__init__(self, *args, **kwargs)
        PersistentPropertyHolder.__init__(self)

    @property
    def containerId(self):
        if self.__parent__ is not None:
            return self.__parent__.NTIID


from zope.deprecation import deprecated

deprecated('Grades', 'No longer used')
class Grades(Persistent):
    pass


@interface.implementer(IPredictedGrade, IContentTypeAware)
class PredictedGrade(object):
    """
    Unrelated to Grade and IGrade: this class represents the
    grade predicted for a student in a course.
    """
    createDirectFieldProperties(IPredictedGrade)

    __external_class_name__ = "PredictedGrade"

    parameters = {}
    mimeType = mime_type = 'application/vnd.nextthought.predictedgrade'

    raw_value = alias('RawValue')
    correctness = alias('Correctness')
    points_earned = alias('PointsEarned')
    points_available = alias('PointsAvailable')

    def __init__(self, points_earned=None, points_available=None, 
                 correctness=None, presentation_scheme=None):
        self.points_earned = points_earned
        self.points_available = points_available

        # If we can calculate a grade from the points values,
        # do that. But if we explicitly specify a correctness
        # value, use that instead.

        if correctness is not None:
            self.raw_value = correctness
            self.correctness = correctness

        elif points_available != 0:
            grade = float(points_earned) / points_available
            self.raw_value = grade
            # Correctness should be bounded such that 0 ≤ result ≤ 1, and
            # rounded to two decimal places.
            self.correctness = round(min(max(0, grade), 1), 2)

        self.presentation = presentation_scheme

    @property
    def Grade(self):
        return self.presentation.fromCorrectness(self.Correctness)
