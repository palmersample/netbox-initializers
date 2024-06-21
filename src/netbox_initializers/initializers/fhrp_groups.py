from ipam.models import FHRPGroup, IPAddress

from . import BaseInitializer, InitializationError, register_initializer

MATCH_PARAMS = ["group_id", "name", "protocol"]  # , "vrf", "vlan"]


class FhrpGroupInitializer(BaseInitializer):
    data_file_name = "fhrp_groups.yml"

    def load_data(self):
        fhrp_groups = self.load_yaml()
        if fhrp_groups is None:
            return
        for params in fhrp_groups:
            custom_field_data = self.pop_custom_fields(params)
            tags = params.pop("tags", None)

            if "protocol" not in params:
                raise InitializationError(
                    f"⚠️ Missing required parameter 'protocol' for FHRP Group {params['group_id']}"
                )

            matching_params, defaults = self.split_params(params, MATCH_PARAMS)
            fhrp_group, created = FHRPGroup.objects.get_or_create(**matching_params, defaults=defaults)

            if created:
                print("📌 Created FHRP Group", fhrp_group.group_id)

            self.set_custom_fields_values(fhrp_group, custom_field_data)
            self.set_tags(fhrp_group, tags)


register_initializer("fhrp_groups", FhrpGroupInitializer)
