from django.utils import timezone
import random
import factory

from vkontakte_groups.factories import GroupFactory
from vkontakte_users.factories import UserFactory

from . models import Album, Photo


class AlbumFactory(factory.DjangoModelFactory):
    FACTORY_FOR = Album

    remote_id = factory.LazyAttributeSequence(lambda o, n: '-%s_%s' % (o.group.remote_id, n))
    thumb_id = factory.Sequence(lambda n: n)

    #owner = factory.SubFactory(GroupFactory)

    created = timezone.now()
    updated = timezone.now()
    size = 1


class PhotoFactory(factory.DjangoModelFactory):
    FACTORY_FOR = Photo

    remote_id = factory.LazyAttributeSequence(lambda o, n: '%s_%s' % (o.group.remote_id, n))
    user = factory.SubFactory(UserFactory)
    album = factory.SubFactory(AlbumFactory)
    #owner = factory.SubFactory(GroupFactory)

    date = timezone.now()
    width = 10
    height = 10
