# HAPPY JARZ US / EU Profiles

US and EU are release/profile lanes, not separate source-code forks.

## Shared source rule

Common features should live in shared firmware/host code.

Region profiles should override only what genuinely differs.

Possible regional differences may include:
- Wi-Fi regulatory behavior
- timezone defaults
- date/time presentation defaults
- locale-specific defaults
- future region-specific compliance settings

Do not duplicate games, LED patterns, input systems or core protocol code merely to make an EU build.

## Provisioning

Region should be written once during setup/manufacturing and persisted in device configuration.

Expected values:

```text
US
EU
```

The updater should preserve that value across normal updates.

## Cat / Europe lane

The EU lane is reserved now so Cat's hardware can be configured without creating a new architecture later.

No EU-specific firmware divergence is claimed yet. Actual differences should be added only when the European hardware/setup is in hand and tested.
