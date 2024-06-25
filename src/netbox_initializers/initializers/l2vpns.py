from dcim.models import Device, Interface
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from ipam.models import VRF, IPAddress, FHRPGroup, RouteTarget, VLAN
from netaddr import IPNetwork
from tenancy.models import Tenant
from virtualization.models import VirtualMachine, VMInterface
from vpn.models import L2VPN, L2VPNTermination

from . import BaseInitializer, InitializationError, register_initializer

MATCH_PARAMS = ["name"]
OPTIONAL_MANY_ASSOCS = {
    "import_targets": (RouteTarget, "name"),
    "export_targets": (RouteTarget, "name"),
}
OPTIONAL_ASSOCS = {
    "tenant": (Tenant, "name"),
}
TERMINATION_ASSOCS = {
    "interface": (Interface, "name"),
    "vlan": (VLAN, "name"),
}

VM_INTERFACE_CT = ContentType.objects.filter(
    Q(app_label="virtualization", model="vminterface")
).first()
INTERFACE_CT = ContentType.objects.filter(Q(app_label="dcim", model="interface")).first()
VLAN_CT = ContentType.objects.filter(Q(app_label="ipam", model="vlan")).first()


class L2VPNInitializer(BaseInitializer):
    data_file_name = "l2vpns.yml"

    def load_data(self):
        l2vpns = self.load_yaml()
        if l2vpns is None:
            return
        for params in l2vpns:
            custom_field_data = self.pop_custom_fields(params)
            tags = params.pop("tags", None)

            for assoc, details in OPTIONAL_ASSOCS.items():
                if assoc in params:
                    model, field = details
                    query = {field: params.pop(assoc)}
                    params[assoc] = model.objects.get(**query)
            #
            # siphon off params that represent many to many relationships
            many_assocs = {}
            for many_assoc in OPTIONAL_MANY_ASSOCS.keys():
                if many_assoc in params:
                    many_assocs[many_assoc] = params.pop(many_assoc)

            matching_params, defaults = self.split_params(params, MATCH_PARAMS)
            l2vpn, created = L2VPN.objects.get_or_create(
                **matching_params, defaults=defaults
            )

            for assoc_field, assocs in many_assocs.items():
                model, field = OPTIONAL_MANY_ASSOCS[assoc_field]
                for assoc in assocs:
                    query = {field: assoc}
                    getattr(l2vpn, assoc_field).add(model.objects.get(**query))

            vm = params.pop("virtual_machine", None)
            device = params.pop("device", None)
            # vlan = params.pop("vlan", None)

            # if vm and device or vlan:
            if (
                (vm and device and params.get("vlan", None)) or
                (vm and device) or
                (vm and params.get("vlan", None)) or
                (device and params.get("vlan", None))
            ):
                raise InitializationError(
                    "L2VPN termination can only specify one of the following: virtual_machine or device or vlan."
                )

            termination_params = {}
            for assoc, details in TERMINATION_ASSOCS.items():
                if assoc in params:
                    model, field = details
                    if assoc == "interface":
                        if vm:
                            vm_id = VirtualMachine.objects.get(name=vm).id
                            query = {"name": params.pop(assoc), "virtual_machine_id": vm_id}
                            termination_params["assigned_object_type"] = VM_INTERFACE_CT
                            termination_params["assigned_object_id"] = VMInterface.objects.get(**query).id
                        elif device:
                            dev_id = Device.objects.get(name=device).id
                            query = {"name": params.pop(assoc), "device_id": dev_id}
                            termination_params["assigned_object_type"] = INTERFACE_CT
                            termination_params["assigned_object_id"] = Interface.objects.get(**query).id
                    elif assoc == "vlan":
                        query = {field: params.pop(assoc)}
                        print(f"VLAN Query: {query}")
                        termination_params["assigned_object_type"] = VLAN_CT
                        termination_params["assigned_object_id"] = VLAN.objects.get(**query).id

                    # elif assoc == "vrf" and params[assoc] is None:
                    #     params["vrf_id"] = None
                    else:
                        query = {field: params.pop(assoc)}

                        termination_params[assoc] = model.objects.get(**query)

                    L2VPNTermination.objects.get_or_create(
                        l2vpn=l2vpn,
                        **termination_params
                    )

            if created:
                print("🧬 Created L2VPN", l2vpn.name)

            self.set_custom_fields_values(l2vpn, custom_field_data)
            self.set_tags(l2vpn, tags)


register_initializer("l2vpns", L2VPNInitializer)
