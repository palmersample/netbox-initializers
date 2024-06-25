from dcim.models import Device, Interface
from ipam.models import VLAN, VRF, FHRPGroup, FHRPGroupAssignment
from django.db.models import Q
from django.contrib.contenttypes.models import ContentType


from . import BaseInitializer, InitializationError, register_initializer

MATCH_PARAMS = ["device", "name"]
REQUIRED_ASSOCS = {"device": (Device, "name")}
OPTIONAL_ASSOCS = {
    "untagged_vlan": (VLAN, "name"),
    "vrf": (VRF, "name"),
}
OPTIONAL_MANY_ASSOCS = {
    "tagged_vlans": (VLAN, "name"),
    "fhrp_groups": (FHRPGroup, "group_id"),
}
RELATED_ASSOCS = {
    "bridge": (Interface, "name"),
    "lag": (Interface, "name"),
    "parent": (Interface, "name"),
}

INTERFACE_CT = ContentType.objects.filter(Q(app_label="dcim", model="interface")).first()


class InterfaceInitializer(BaseInitializer):
    data_file_name = "interfaces.yml"

    def load_data(self):
        interfaces = self.load_yaml()
        if interfaces is None:
            return
        for params in interfaces:
            custom_field_data = self.pop_custom_fields(params)
            tags = params.pop("tags", None)

            related_interfaces = {k: params.pop(k, None) for k in RELATED_ASSOCS}

            for assoc, details in REQUIRED_ASSOCS.items():
                model, field = details
                query = {field: params.pop(assoc)}

                params[assoc] = model.objects.get(**query)

            for assoc, details in OPTIONAL_ASSOCS.items():
                if assoc in params:
                    model, field = details
                    query = {field: params.pop(assoc)}

                    params[assoc] = model.objects.get(**query)

            # siphon off params that represent many to many relationships
            many_assocs = {}
            for many_assoc in OPTIONAL_MANY_ASSOCS.keys():
                if many_assoc in params:
                    many_assocs[many_assoc] = params.pop(many_assoc)

            matching_params, defaults = self.split_params(params, MATCH_PARAMS)
            interface, created = Interface.objects.get_or_create(
                **matching_params, defaults=defaults
            )

            # process the one to many relationships
            for assoc_field, assocs in many_assocs.items():
                model, field = OPTIONAL_MANY_ASSOCS[assoc_field]
                if assoc_field == "fhrp_groups":
                    for assoc in assocs:
                        if not all((assoc["group_id"], assoc["priority"], )):
                            raise InitializationError(
                                "FHRP Group assignment requires fields 'group_id' and 'priority' to be defined."
                            )
                        query = {field: assoc["group_id"]}
                        FHRPGroupAssignment.objects.get_or_create(
                            interface_type=INTERFACE_CT,
                            interface_id=interface.id,
                            group=model.objects.get(**query),
                            priority=assoc["priority"]
                        )
                else:
                    for assoc in assocs:
                        query = {field: assoc}
                        getattr(interface, assoc_field).add(model.objects.get(**query))

            if created:
                print(f"🧷 Created interface {interface} on {interface.device}")
            else:
                for name in defaults:
                    setattr(interface, name, defaults[name])
                interface.save()

            self.set_custom_fields_values(interface, custom_field_data)
            self.set_tags(interface, tags)

            for related_field, related_value in related_interfaces.items():
                if not related_value:
                    continue

                r_model, r_field = RELATED_ASSOCS[related_field]

                if related_field == "parent" and not interface.parent_id:
                    query = {r_field: related_value, "device": interface.device}
                    try:
                        related_obj = r_model.objects.get(**query)
                    except Interface.DoesNotExist:
                        print(
                            f"⚠️ Could not find parent interface with: {query} for interface {interface}"
                        )
                        raise

                    interface.parent_id = related_obj.id
                    interface.save()
                    print(
                        f"🧷 Attached interface {interface} on {interface.device} "
                        f"to parent {related_obj}"
                    )
                else:
                    query = {
                        r_field: related_value,
                        "device": interface.device,
                    }
                    related_obj, rel_obj_created = r_model.objects.get_or_create(**query)

                    if rel_obj_created:
                        print(
                            f"🧷 Created {related_field} interface {interface} on {interface.device}"
                        )

                    setattr(interface, f"{related_field}_id", related_obj.id)
                    interface.save()


register_initializer("interfaces", InterfaceInitializer)
