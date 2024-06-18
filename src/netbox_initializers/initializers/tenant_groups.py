from tenancy.models import TenantGroup

from . import BaseInitializer, register_initializer

OPTIONAL_ASSOCS = {"parent": (TenantGroup, "name")}


class TenantGroupInitializer(BaseInitializer):
    data_file_name = "tenant_groups.yml"

    def load_data(self):
        tenant_groups = self.load_yaml()
        if tenant_groups is None:
            return
        for params in tenant_groups:
            tags = params.pop("tags", None)

            for assoc, details in OPTIONAL_ASSOCS.items():
                if assoc in params:
                    model, field = details
                    query = {field: params.pop(assoc)}

                    params[assoc] = model.objects.get(**query)

            matching_params, defaults = self.split_params(params)
            tenant_group, created = TenantGroup.objects.get_or_create(
                **matching_params, defaults=defaults
            )

            if created:
                print("🔳 Created Tenant Group", tenant_group.name)

            self.set_tags(tenant_group, tags)


register_initializer("tenant_groups", TenantGroupInitializer)
