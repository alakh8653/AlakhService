import 'package:flutter/material.dart';

import '../l10n/l10n.dart';

/// The groups service types are shown under.
enum ServiceGroup { beauty, health, homeRepairs, homeHelp, vehicles, learning, events, other }

/// A kind of work people book: what a business says it does, and what customers browse by. The id is the
/// shop's category on the server; every service of the shop is found under it, whatever it is called.
class ServiceType {
  final String id;
  final IconData icon;
  final ServiceGroup group;
  final String Function(AppLocalizations) label;

  /// Subcategories to pick with a tap, in English as the catalogue is (customers search it in English).
  final List<String> suggestions;

  const ServiceType(this.id, this.icon, this.group, this.label, this.suggestions);
}

String serviceGroupLabel(ServiceGroup group, AppLocalizations l) => switch (group) {
      ServiceGroup.beauty => l.groupBeauty,
      ServiceGroup.health => l.groupHealth,
      ServiceGroup.homeRepairs => l.groupHomeRepairs,
      ServiceGroup.homeHelp => l.groupHomeHelp,
      ServiceGroup.vehicles => l.groupVehicles,
      ServiceGroup.learning => l.groupLearning,
      ServiceGroup.events => l.groupEvents,
      ServiceGroup.other => l.groupOther,
    };

/// In the order shown. Existing ids must not change: shops are stored with them. Keep in step with the shop
/// dashboard's services/categories.ts.
final List<ServiceType> serviceTypes = [
  ServiceType('salon', Icons.content_cut, ServiceGroup.beauty, (l) => l.categorySalon, const ['Haircut', 'Kids haircut', 'Beard trim', 'Shave', 'Hair colour', 'Hair spa', 'Hair straightening', 'Head massage', 'Facial for men', 'Haircut at home']),
  ServiceType('beauty', Icons.face_retouching_natural, ServiceGroup.beauty, (l) => l.categoryBeauty, const ['Facial', 'Cleanup', 'Threading', 'Waxing', 'Manicure', 'Pedicure', 'Bleach', 'Party makeup', 'Bridal makeup', 'Saree draping', 'Hair styling']),
  ServiceType('spa', Icons.spa, ServiceGroup.beauty, (l) => l.categorySpa, const ['Full body massage', 'Foot massage', 'Head and shoulder massage', 'Body scrub', 'Ayurvedic massage', 'Massage at home']),
  ServiceType('mehndi', Icons.back_hand_outlined, ServiceGroup.beauty, (l) => l.typeMehndi, const ['Mehndi for hands', 'Bridal mehndi', 'Party mehndi', 'Festival mehndi']),
  ServiceType('tailoring', Icons.checkroom, ServiceGroup.beauty, (l) => l.typeTailoring, const ['Blouse stitching', 'Suit stitching', 'Kurta stitching', 'Pant and shirt stitching', 'Lehenga stitching', 'Alterations', 'Fall and pico']),
  ServiceType('clinic', Icons.medical_services, ServiceGroup.health, (l) => l.categoryClinic, const ['Consultation', 'Follow-up visit', 'Home visit by doctor', 'Online consultation', 'Child specialist', 'Skin specialist', 'Women\'s health', 'Bone and joint', 'Ayurveda consultation', 'Homeopathy consultation', 'Health certificate']),
  ServiceType('dentist', Icons.mood, ServiceGroup.health, (l) => l.typeDentist, const ['Dental check-up', 'Teeth cleaning', 'Tooth filling', 'Tooth removal', 'Root canal', 'Braces consultation', 'Teeth whitening', 'Dentures']),
  ServiceType('physiotherapy', Icons.accessibility_new, ServiceGroup.health, (l) => l.typePhysiotherapy, const ['Physiotherapy session', 'Home physiotherapy', 'Back and neck pain', 'Knee pain', 'After-surgery care', 'Stroke recovery']),
  ServiceType('home_nursing', Icons.health_and_safety, ServiceGroup.health, (l) => l.typeHomeNursing, const ['Nurse visit', 'Injection at home', 'IV drip at home', 'Dressing at home', 'Catheter care', 'Blood pressure and sugar check', '12-hour nurse', '24-hour nurse', 'Mother and baby care']),
  ServiceType('lab_tests', Icons.biotech, ServiceGroup.health, (l) => l.typeLabTests, const ['Blood test', 'Sample collection at home', 'Health check-up', 'Diabetes test', 'Thyroid test', 'Urine test', 'ECG at home']),
  ServiceType('pet_care', Icons.pets, ServiceGroup.health, (l) => l.typePetCare, const ['Vet consultation', 'Vet visit at home', 'Vaccination', 'Pet grooming', 'Pet bathing', 'Dog walking', 'Pet boarding', 'Dog training']),
  ServiceType('electrical', Icons.electrical_services, ServiceGroup.homeRepairs, (l) => l.categoryElectrical, const ['Fan repair', 'Fan installation', 'Switch or socket repair', 'Light fitting', 'Wiring work', 'New house wiring', 'MCB or fuse repair', 'Inverter installation', 'Geyser installation', 'Doorbell fitting', 'TV wall mounting', 'Earthing work']),
  ServiceType('plumbing', Icons.plumbing, ServiceGroup.homeRepairs, (l) => l.categoryPlumbing, const ['Tap repair', 'Tap installation', 'Pipe leak repair', 'Toilet repair', 'Toilet installation', 'Blocked drain cleaning', 'Water tank cleaning', 'Water tank installation', 'Motor pump repair', 'Bathroom fitting', 'Geyser pipe fitting', 'New pipeline work']),
  ServiceType('carpentry', Icons.carpenter, ServiceGroup.homeRepairs, (l) => l.typeCarpentry, const ['Door repair', 'Lock fitting', 'Furniture repair', 'Furniture making', 'Bed or wardrobe assembly', 'Modular kitchen work', 'Window repair', 'Curtain rod fitting', 'Shelf fitting']),
  ServiceType('appliance_repair', Icons.ac_unit, ServiceGroup.homeRepairs, (l) => l.categoryApplianceRepair, const ['AC service', 'AC gas filling', 'AC repair', 'AC installation', 'AC uninstallation', 'Fridge repair', 'Washing machine repair', 'Microwave repair', 'Geyser repair', 'Chimney repair', 'Chimney cleaning', 'TV repair', 'Gas stove repair', 'Mixer or iron repair']),
  ServiceType('water_purifier', Icons.water_drop_outlined, ServiceGroup.homeRepairs, (l) => l.typeWaterPurifier, const ['RO service', 'RO repair', 'RO installation', 'Filter change', 'Annual maintenance']),
  ServiceType('painting', Icons.format_paint, ServiceGroup.homeRepairs, (l) => l.typePainting, const ['Room painting', 'Full home painting', 'Outside wall painting', 'Waterproofing', 'Wood polish', 'Wallpaper fitting', 'Texture painting', 'Putty work']),
  ServiceType('pest_control', Icons.pest_control, ServiceGroup.homeRepairs, (l) => l.typePestControl, const ['Cockroach control', 'Termite control', 'Mosquito control', 'Bed bug control', 'Rat control', 'Ant control', 'Full home pest control']),
  ServiceType('repair', Icons.handyman, ServiceGroup.homeRepairs, (l) => l.categoryRepair, const ['Handyman visit', 'Lock repair', 'Small home repairs', 'Picture and shelf fitting', 'Furniture assembly', 'Grill and door repair']),
  ServiceType('construction', Icons.foundation, ServiceGroup.homeRepairs, (l) => l.typeConstruction, const ['Mason work', 'Full house construction', 'Room addition', 'House renovation', 'Bathroom renovation', 'Kitchen renovation', 'Tile and marble fitting', 'Plastering', 'Brick work', 'Roof work', 'Waterproofing work', 'Labour for the day', 'Demolition', 'Borewell work', 'Site supervision']),
  ServiceType('welding', Icons.hardware, ServiceGroup.homeRepairs, (l) => l.typeWelding, const ['Gate making', 'Grill making', 'Gate or grill repair', 'Shed making', 'Staircase railing', 'Aluminium window work', 'Steel furniture repair']),
  ServiceType('interior', Icons.chair_outlined, ServiceGroup.homeRepairs, (l) => l.typeInterior, const ['Home interior design', 'False ceiling', 'POP work', 'Modular kitchen design', 'Wardrobe design', 'Office interior', 'Glass partition']),
  ServiceType('solar', Icons.solar_power_outlined, ServiceGroup.homeRepairs, (l) => l.typeSolar, const ['Solar panel installation', 'Solar panel cleaning', 'Solar repair', 'Inverter repair', 'Battery replacement', 'Solar water heater']),
  ServiceType('cleaning', Icons.cleaning_services, ServiceGroup.homeHelp, (l) => l.categoryCleaning, const ['Home deep cleaning', 'Bathroom cleaning', 'Kitchen cleaning', 'Sofa cleaning', 'Carpet cleaning', 'Mattress cleaning', 'Water tank cleaning', 'Office cleaning', 'After-construction cleaning', 'Move-in cleaning', 'Car interior cleaning']),
  ServiceType('domestic_help', Icons.house_outlined, ServiceGroup.homeHelp, (l) => l.typeDomesticHelp, const ['House help', 'Utensil and floor cleaning', 'Full-time house help', 'Part-time house help', 'Live-in help']),
  ServiceType('cook', Icons.soup_kitchen_outlined, ServiceGroup.homeHelp, (l) => l.typeCook, const ['Home cook', 'Daily cook', 'Cook for a party', 'North Indian cook', 'South Indian cook', 'Tiffin service']),
  ServiceType('care_giver', Icons.elderly, ServiceGroup.homeHelp, (l) => l.typeCareGiver, const ['Elder care', 'Baby care', 'Patient care at home', 'Nanny', 'Day care', 'Night attendant']),
  ServiceType('security_guard', Icons.security, ServiceGroup.homeHelp, (l) => l.typeSecurityGuard, const ['Security guard for the day', 'Monthly security guard', 'Event security', 'Society security', 'Night watchman']),
  ServiceType('laundry', Icons.local_laundry_service, ServiceGroup.homeHelp, (l) => l.typeLaundry, const ['Wash and iron', 'Dry cleaning', 'Ironing', 'Shoe cleaning', 'Blanket and curtain washing', 'Pickup and delivery']),
  ServiceType('gardening', Icons.yard_outlined, ServiceGroup.homeHelp, (l) => l.typeGardening, const ['Garden care', 'Plant care', 'Lawn cutting', 'Terrace garden setup', 'Tree trimming', 'New plants and pots']),
  ServiceType('packers_movers', Icons.local_shipping_outlined, ServiceGroup.homeHelp, (l) => l.typePackersMovers, const ['House shifting', 'Office shifting', 'Goods transport', 'Vehicle transport', 'Packing only', 'Loading and unloading labour']),
  ServiceType('vehicle_repair', Icons.car_repair, ServiceGroup.vehicles, (l) => l.categoryVehicleRepair, const ['Car service', 'Car repair', 'Bike service', 'Bike repair', 'Puncture repair', 'Battery change', 'Denting and painting', 'Car AC repair', 'Engine work', 'Brake repair', 'Wheel alignment', 'Car breakdown help', 'Bike breakdown help']),
  ServiceType('car_wash', Icons.local_car_wash, ServiceGroup.vehicles, (l) => l.typeCarWash, const ['Car wash', 'Bike wash', 'Interior cleaning', 'Car polish', 'Ceramic coating', 'Wash at home']),
  ServiceType('driver', Icons.drive_eta_outlined, ServiceGroup.vehicles, (l) => l.typeDriver, const ['Driver for the day', 'Driver for a trip', 'Monthly driver', 'Outstation driver', 'Night driver']),
  ServiceType('electronics_repair', Icons.devices, ServiceGroup.other, (l) => l.categoryElectronicsRepair, const ['Mobile screen replacement', 'Mobile battery replacement', 'Laptop repair', 'Computer repair', 'CCTV installation', 'CCTV repair', 'Printer repair', 'Wi-Fi setup', 'Data recovery']),
  ServiceType('tutor', Icons.school_outlined, ServiceGroup.learning, (l) => l.typeTutor, const ['Home tuition', 'Maths tuition', 'Science tuition', 'English tuition', 'Spoken English', 'Exam coaching', 'Computer classes', 'Online tuition']),
  ServiceType('fitness', Icons.fitness_center, ServiceGroup.learning, (l) => l.typeFitness, const ['Yoga class', 'Personal trainer', 'Zumba class', 'Home yoga', 'Diet plan', 'Meditation class']),
  ServiceType('music_dance', Icons.music_note_outlined, ServiceGroup.learning, (l) => l.typeMusicDance, const ['Music class', 'Guitar class', 'Singing class', 'Dance class', 'Wedding choreography']),
  ServiceType('photography', Icons.photo_camera_outlined, ServiceGroup.events, (l) => l.typePhotography, const ['Wedding photography', 'Pre-wedding shoot', 'Event photography', 'Photo session', 'Baby shoot', 'Video shooting', 'Drone shoot', 'Photo editing']),
  ServiceType('catering', Icons.restaurant_outlined, ServiceGroup.events, (l) => l.typeCatering, const ['Party catering', 'Wedding catering', 'Office lunch', 'Birthday food', 'Sweets and snacks order']),
  ServiceType('event_decor', Icons.celebration_outlined, ServiceGroup.events, (l) => l.typeEventDecor, const ['Birthday decoration', 'Wedding decoration', 'Balloon decoration', 'Flower decoration', 'Stage setup', 'Tent and chairs', 'DJ and sound', 'Lighting']),
  ServiceType('priest', Icons.temple_hindu_outlined, ServiceGroup.events, (l) => l.typePriest, const ['Griha pravesh puja', 'Satyanarayan puja', 'Wedding ceremony', 'Havan', 'Naming ceremony', 'Online puja']),
  ServiceType('tax_legal', Icons.gavel_outlined, ServiceGroup.other, (l) => l.typeTaxLegal, const ['ITR filing', 'GST registration', 'GST filing', 'Company registration', 'Accounting', 'Legal advice', 'Notary work', 'Property documents']),
  ServiceType('office', Icons.event_available, ServiceGroup.other, (l) => l.categoryOffice, const ['Appointment', 'Consultation', 'Document work']),
  ServiceType('other', Icons.more_horiz, ServiceGroup.other, (l) => l.categoryOther, const []),
];

/// How long a job usually takes, as the starting value: work at the customer's place takes longer.
int usualMinutes(ServiceType? type) => switch (type?.group) {
      ServiceGroup.homeRepairs || ServiceGroup.homeHelp || ServiceGroup.vehicles || ServiceGroup.events => 60,
      _ => 30,
    };

ServiceType? serviceTypeById(String id) {
  for (final type in serviceTypes) {
    if (type.id == id) return type;
  }
  return null;
}

/// What most people look for first, on the home screen; the rest are one tap away in All services.
const homeServiceTypeIds = [
  'salon',
  'beauty',
  'clinic',
  'electrical',
  'plumbing',
  'appliance_repair',
  'cleaning',
  'carpentry',
  'vehicle_repair',
  'electronics_repair',
  'tutor',
];
