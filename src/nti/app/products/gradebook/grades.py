#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grades definition

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from persistent import Persistent

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from zope.container.ordered import OrderedContainer

from zope.location.interfaces import ISublocations

from zope.mimetype.interfaces import IContentTypeAware

from nti.app.products.gradebook.interfaces import IGrade, IGradeContainer

from nti.base.interfaces import ICreated

from nti.contenttypes.courses.grading.interfaces import IPredictedGrade

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_denying_all

from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dublincore.datastructures import CreatedModDateTrackingObject
from nti.dublincore.datastructures import PersistentCreatedModDateTrackingObject

from nti.externalization.representation import WithRepr

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

from nti.wref.interfaces import IWeakRef

from nti.zodb.persistentproperty import PersistentPropertyHolder

logger = __import__('logging').getLogger(__name__)


@WithRepr
@interface.implementer(IGrade)
@EqHash('username', 'assignmentId', 'value')
class Grade(CreatedModDateTrackingObject,
            SchemaConfigured,
            Contained):

    createDirectFieldProperties(IGrade)

    grade = alias('value')
    username = alias('Username')
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
        super(Grade, self).__init__(*args, **kwargs)

    @Lazy
    def createdTime(self):  # pylint: disable=method-hidden
        # Some old objects in the database won't have a value for
        # created time; in that case, default to lastModified.
        # Some old objects in the database will have a lastModified
        # of 0, though, nothing we can do about that...
        return self.lastModified

    @property
    def AssignmentId(self):
        if self.__parent__ is not None:
            return self.__parent__.AssignmentId

    @property
    def HistoryItemNTIID(self):
        return self.__name__

    @property
    def Username(self):
        if self.__parent__ is not None:
            return self.__parent__.__name__

    # Since we're not persistent, the regular use of CachedProperty fails
    @property
    def __acl__(self):
        acl = acl_from_aces()
        course = ICourseInstance(self, None)
        if course is not None:
            # pylint: disable=not-an-iterable
            acl.extend(ace_allowing(i, ALL_PERMISSIONS)
                       for i in course.instructors or ())
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

    __slots__ = ('_part_wref', '_key')

    def __init__(self, grade):
        if grade.__parent__ is None or not grade.__name__:
            raise TypeError("Too soon, grade has no parent or key")
        self._key = grade.__name__
        self._part_wref = IWeakRef(grade.__parent__)

    def __call__(self):
        part = self._part_wref()
        if part is not None:
            return part.get(self._key)

    def __eq__(self, other):
        # pylint: disable=protected-access
        try:
            return self is other \
                or (self._key, self._part_wref) == (other._key, other._part_wref)
        except AttributeError:
            return NotImplemented

    def __hash__(self):
        return hash((self._key, self._part_wref))

    def __getstate__(self):
        return self._part_wref, self._key

    def __setstate__(self, state):
        self._part_wref, self._key = state


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


@interface.implementer(IGradeContainer,
                       ISublocations)
class GradeContainer(PersistentCreatedModDateTrackingObject,
                     OrderedContainer,
                     Contained,
                     SchemaConfigured):

    createDirectFieldProperties(IGradeContainer)

    __external_can_create__ = False

    assignmentId = alias('AssignmentId')
    username = alias('Username')

    @property
    def Items(self):
        return list(self.values())

    def sublocations(self):
        return tuple(self.values())

    @property
    def AssignmentId(self):
        if self.__parent__ is not None:
            return self.__parent__.AssignmentId

    @property
    def Username(self):
        return self.__name__

#     @property
#     def creator(self):
#         return self.__parent__.creator
#
#     @creator.setter
#     def creator(self, nv):
#         pass

    def reset(self, event=True):
        keys = list(self)
        for k in keys:
            if event:
                del self[k]  # pylint: disable=unsupported-delete-operation
            else:
                self._delitemf(k)
    clear = reset


@interface.implementer(IPredictedGrade, IContentTypeAware)
class PredictedGrade(object):
    """
    Unrelated to Grade and IGrade: this class represents the
    grade predicted for a student in a course.
    """
    createDirectFieldProperties(IPredictedGrade)

    __external_class_name__ = "PredictedGrade"

    mimeType = mime_type = 'application/vnd.nextthought.predictedgrade'

    parameters = {}

    raw_value = alias('RawValue')
    correctness = alias('Correctness')
    points_earned = alias('PointsEarned')
    points_available = alias('PointsAvailable')

    def __init__(self, points_earned=None, points_available=None,
                 raw_value=None, presentation_scheme=None):
        if raw_value is not None:
            self.RawValue = raw_value
        self.PointsEarned = points_earned
        self.PointsAvailable = points_available
        self.Presentation = presentation_scheme

    @property
    def Grade(self):
        if self.RawValue is not None and self.Presentation is not None:
            return self.Presentation.fromCorrectness(self)
        return None

    @Lazy
    def RawValue(self):  # pylint: disable=method-hidden
        if     self.PointsAvailable == 0 \
            or self.PointsAvailable is None \
            or self.PointsEarned is None:
            return None
        return float(self.PointsEarned) / self.PointsAvailable

    @Lazy
    def Correctness(self):
        if self.RawValue is not None:
            return int(round(min(max(0, self.RawValue), 1), 2) * 100)
        return None

    @property
    def DisplayableGrade(self):
        if self.Presentation is not None:
            return self.Presentation.toDisplayableGrade(self)
        return self.Correctness


from zope.deprecation import deprecated

deprecated('Grades', 'No longer used')
class Grades(Persistent):
    pass
