# Copyright (c) 2016 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the License);
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an AS IS BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and#
# limitations under the License.
import heapq

from cloudferrylib.os.discovery import nova
from cloudferrylib.os.discovery import cinder
from cloudferrylib.os.discovery import glance
from cloudferrylib.os.discovery import model
from cloudferrylib.utils import sizeof_format


def list_filtered(tx, cls, cloud_name, tenant):
    return (x for x in tx.list(cls, cloud_name)
            if tenant is None or tenant == x.tenant.object_id.id)


def estimate_copy(cloud_name, tenant):
    with model.Transaction() as tx:
        total_ephemeral_size = 0
        total_volume_size = 0
        total_image_size = 0
        accounted_volumes = set()
        accounted_images = set()

        for server in list_filtered(tx, nova.Server, cloud_name, tenant):
            for ephemeral_disk in server.ephemeral_disks:
                total_ephemeral_size += ephemeral_disk.size
            if server.image is not None \
                    and server.image.object_id not in accounted_images:
                total_image_size += server.image.size
                accounted_images.add(server.image.object_id)
            for volume in server.attached_volumes:
                if volume.object_id not in accounted_volumes:
                    total_volume_size += volume.size
                    accounted_volumes.add(volume.object_id)
        for volume in list_filtered(tx, cinder.Volume, cloud_name, tenant):
            if volume.object_id not in accounted_volumes:
                total_volume_size += volume.size
        for image in list_filtered(tx, glance.Image, cloud_name, tenant):
            if image.object_id not in accounted_images:
                total_image_size += image.size

    print 'Images:'
    print '  Size:', sizeof_format.sizeof_fmt(total_image_size)
    print 'Ephemeral disks:'
    print '  Size:', sizeof_format.sizeof_fmt(total_ephemeral_size)
    print 'Volumes:'
    print '  Size:', sizeof_format.sizeof_fmt(total_volume_size, 'G')


def show_largest_servers(count, cloud_name, tenant):
    def server_size(server):
        size = 0
        if server.image is not None:
            size += server.image.size
        for ephemeral_disk in server.ephemeral_disks:
            size += ephemeral_disk.size
        for volume in server.attached_volumes:
            size += volume.size
        return size

    output = []
    with model.Transaction() as tx:
        for index, server in enumerate(
                heapq.nlargest(
                    count,
                    list_filtered(tx, nova.Server, cloud_name, tenant),
                    key=server_size),
                start=1):
            output.append(
                '  {0}. {1.object_id.id} {1.name}'.format(index, server))
    if output:
        print '\n{0} largest servers:'.format(len(output))
        for line in output:
            print line


def show_largest_unused_resources(count, cloud_name, tenant):
    with model.Transaction() as tx:
        used_volumes = set()
        used_images = set()
        servers = list_filtered(tx, nova.Server, cloud_name, tenant)
        for server in servers:
            if server.image is not None:
                used_images.add(server.image.object_id)
            for volume in server.attached_volumes:
                used_volumes.add(volume.object_id)

        # Find unused volumes
        volumes_output = []
        volumes_size = 0
        volumes = list_filtered(tx, cinder.Volume, cloud_name, tenant)
        for index, volume in enumerate(
                heapq.nlargest(count,
                               (v for v in volumes
                                if v.object_id not in used_volumes),
                               key=lambda v: v.size),
                start=1):
            volumes_size += volume.size
            size = sizeof_format.sizeof_fmt(volume.size, 'G')
            volumes_output.append(
                '  {0:3d}. {1.object_id.id} {2:10s} {1.name}'.format(
                    index, volume, size))

        # Find unused images
        images_output = []
        images_size = 0
        images = list_filtered(tx, glance.Image, cloud_name, tenant)
        for index, image in enumerate(
                heapq.nlargest(count,
                               (i for i in images
                                if i.object_id not in used_images)),
                start=1):
            images_size += image.size
            size = sizeof_format.sizeof_fmt(image.size)
            images_output.append(
                '  {0:3d}. {1.object_id.id} {2:10s} {1.name}'.format(
                    index, image, size))

    # Output result
    if volumes_output:
        print '\n{0} largest unused volumes:'.format(len(volumes_output))
        for line in volumes_output:
            print line
        print '  Total:', sizeof_format.sizeof_fmt(volumes_size, 'G')
    if images_output:
        print '\n{0} largest unused images:'.format(len(images_output))
        for line in images_output:
            print line
        print '  Total:', sizeof_format.sizeof_fmt(images_size)
