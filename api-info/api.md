## API

(NOT ENTIRELY COMPLETE)

GET https://mypagesapi.sectoralarm.net/api/Panel/GetPanel?panelId=xxxPANELIDxxx HTTP/1.1
Request: Authorization
Response:
```json
{
    "Access": [
        "History",
        "Directions",
        "SecurityQuestion",
        "ContactPersons",
        "AlarmSystemSettings",
        "LockSettings",
        "SmartplugSettings",
        "Photos",
        "Smartplugs",
        "Cameras",
        "CameraSettings",
        "PanelUsers",
        "AddProducts",
        "AppUserSettings",
        "PreInstallationSettings"
    ],
    "BookedEndDate": "0001-01-01T00:00:00",
    "BookedStartDate": "0001-01-01T00:00:00",
    "CanAddDoorLock": false,
    "CanAddSmartplug": false,
    "CanChangeInstallationDate": false,
    "CanPartialArm": true,
    "DisplayName": "xxxDisplayNamexxx",
    "DisplayWizard": false,
    "HasAnnex": false,
    "HasVideo": false,
    "InstallationAddress": null,
    "InstallationStatus": 3,
    "InterviewDisplayStatus": false,
    "LockLanguage": 6,
    "Locks": [
        {
            "AutoLockEnabled": true,
            "Label": "Easylock",
            "Languages": null,
            "PanelId": null,
            "Serial": "xxxLOCKSERIALxxx",
            "SoundLevel": 2,
            "Status": ""
        }
    ],
    "PanelCodeLength": 6,
    "PanelId": "xxxPANELIDxxx",
    "Photos": [],
    "PreInstallationWizardDone": false,
    "PropertyContact": {
        "AccessGroup": 1,
        "AddSmartPlugUserOverride": false,
        "AppUserId": "xxxAppUserIDxxx",
        "FirstName": "xxxFirstnamexxx",
        "IsInvite": false,
        "IsPropertyContact": true,
        "LastName": "xxxLastnamexxx",
        "PhoneNumber": "xxxPhoneNumberxxx"
    },
    "QuickArmEnabled": false,
    "Smartplugs": [],
    "SupportsPanelUsers": true,
    "SupportsRegisterDevices": true,
    "SupportsTemporaryPanelUsers": true,
    "Temperatures": [
        {
            "DeviceId": null,
            "Id": null,
            "Label": "Kök",
            "SerialNo": "xxxTEMPSERIALxxx",
            "Temprature": ""
        },
        {
            "DeviceId": null,
            "Id": null,
            "Label": "Övervåning",
            "SerialNo": "xxxTEMPSERIALxxx",
            "Temprature": ""
        }
    ],
    "Wifi": null,
    "WizardStep": 0
}
```
GET https://mypagesapi.sectoralarm.net/api/Panel/GetPanelStatus?panelId=xxxPANELIDxxx HTTP/1.1
Request: Authorization
Response:
```json
{
    "AnnexStatus": 0,
    "IsOnline": true,
    "Status": 1,
    "StatusTime": "2020-04-29T12:10:08"
}
```

GET https://mypagesapi.sectoralarm.net/api/Panel/GetLockStatus?panelId=xxxPANELIDxxx HTTP/1.1
Request: Authorization
Response:
```json
[
    {
        "AutoLockEnabled": false,
        "Label": null,
        "Languages": null,
        "PanelId": "xxxPANELIDxxx",
        "Serial": "xxxLOCKSERIALxxx",
        "SoundLevel": 0,
        "Status": "lock"
    }
]
```

GET https://mypagesapi.sectoralarm.net/api/Panel/GetTemperatures?panelId=xxxPANELIDxxx HTTP/1.1
Request: Authorization
Response:
```json
[
    {
        "DeviceId": null,
        "Id": null,
        "Label": "Kök",
        "SerialNo": "xxxTEMPSERIALxxx",
        "Temprature": "20"
    },
    {
        "DeviceId": null,
        "Id": null,
        "Label": "Övervåning",
        "SerialNo": "xxxTEMPSERIALxxx",
        "Temprature": "23"
    }
]
```

POST https://mypagesapi.sectoralarm.net/api/Panel/Unlock HTTP/1.1
Request: Authorization
POST:
```json
{
    "LockSerial": "xxxLOCKSERIALxxx",
    "PanelCode": "xxxCODExxx",
    "PanelId": "xxxPANELIDxxx",
    "Platform": "app"
}
```

POST https://mypagesapi.sectoralarm.net/api/Panel/Lock HTTP/1.1
Request: Authorization
POST:
```json
{
    "LockSerial": "xxxLOCKSERIALxxx",
    "PanelCode": "xxxCODExxx",
    "PanelId": "xxxPANELIDxxx",
    "Platform": "app"
}
```

POST https://mypagesapi.sectoralarm.net/api/Panel/PartialArm HTTP/1.1
Request: Authorization
POST:
```json
{
    "PanelCode": "xxxCODExxx",
    "PanelId": "xxxPANELIDxxx",
    "Platform": "app"
}
```

POST https://mypagesapi.sectoralarm.net/api/Panel/Disarm HTTP/1.1
Request: Authorization
POST:
```json
{
    "PanelCode": "xxxCODExxx",
    "PanelId": "xxxPANELIDxxx",
    "Platform": "app"
}
```

POST https://mypagesapi.sectoralarm.net/api/Panel/Arm HTTP/1.1
Request: Authorization
POST:
```json
{
    "PanelCode": "xxxCODExxx",
    "PanelId": "xxxPANELIDxxx",
    "Platform": "app"
}
```
