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

  /// Common services to add with a tap, in English as the catalogue is (customers search it in English).
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
  ServiceType('salon', Icons.content_cut, ServiceGroup.beauty, (l) => l.categorySalon, const ['Haircut', 'Beard trim', 'Hair colour', 'Head massage']),
  ServiceType('beauty', Icons.face_retouching_natural, ServiceGroup.beauty, (l) => l.categoryBeauty, const ['Facial', 'Threading', 'Waxing', 'Bridal makeup']),
  ServiceType('spa', Icons.spa, ServiceGroup.beauty, (l) => l.categorySpa, const ['Full body massage', 'Foot massage', 'Body scrub']),
  ServiceType('mehndi', Icons.back_hand_outlined, ServiceGroup.beauty, (l) => l.typeMehndi, const ['Mehndi for hands', 'Bridal mehndi']),
  ServiceType('tailoring', Icons.checkroom, ServiceGroup.beauty, (l) => l.typeTailoring, const ['Blouse stitching', 'Suit stitching', 'Alterations']),
  ServiceType('clinic', Icons.medical_services, ServiceGroup.health, (l) => l.categoryClinic, const ['Consultation', 'Follow-up visit', 'Home visit by doctor']),
  ServiceType('dentist', Icons.mood, ServiceGroup.health, (l) => l.typeDentist, const ['Dental check-up', 'Teeth cleaning', 'Tooth filling']),
  ServiceType('physiotherapy', Icons.accessibility_new, ServiceGroup.health, (l) => l.typePhysiotherapy, const ['Physiotherapy session', 'Home physiotherapy']),
  ServiceType('home_nursing', Icons.health_and_safety, ServiceGroup.health, (l) => l.typeHomeNursing, const ['Nurse visit', 'Injection at home', 'Dressing at home']),
  ServiceType('lab_tests', Icons.biotech, ServiceGroup.health, (l) => l.typeLabTests, const ['Blood test', 'Sample collection at home', 'Health check-up']),
  ServiceType('pet_care', Icons.pets, ServiceGroup.health, (l) => l.typePetCare, const ['Vet consultation', 'Pet grooming', 'Vaccination']),
  ServiceType('electrical', Icons.electrical_services, ServiceGroup.homeRepairs, (l) => l.categoryElectrical, const ['Fan repair', 'Switch or socket repair', 'Wiring work', 'Light fitting']),
  ServiceType('plumbing', Icons.plumbing, ServiceGroup.homeRepairs, (l) => l.categoryPlumbing, const ['Tap repair', 'Pipe leak repair', 'Toilet repair', 'Water tank cleaning']),
  ServiceType('carpentry', Icons.carpenter, ServiceGroup.homeRepairs, (l) => l.typeCarpentry, const ['Door repair', 'Furniture repair', 'Furniture making']),
  ServiceType('appliance_repair', Icons.ac_unit, ServiceGroup.homeRepairs, (l) => l.categoryApplianceRepair, const ['AC service', 'AC repair', 'Fridge repair', 'Washing machine repair']),
  ServiceType('water_purifier', Icons.water_drop_outlined, ServiceGroup.homeRepairs, (l) => l.typeWaterPurifier, const ['RO service', 'RO repair', 'Filter change']),
  ServiceType('painting', Icons.format_paint, ServiceGroup.homeRepairs, (l) => l.typePainting, const ['Room painting', 'Full home painting', 'Waterproofing']),
  ServiceType('pest_control', Icons.pest_control, ServiceGroup.homeRepairs, (l) => l.typePestControl, const ['Cockroach control', 'Termite control', 'Mosquito control']),
  ServiceType('repair', Icons.handyman, ServiceGroup.homeRepairs, (l) => l.categoryRepair, const ['Handyman visit', 'Lock repair', 'Small home repairs']),
  ServiceType('cleaning', Icons.cleaning_services, ServiceGroup.homeHelp, (l) => l.categoryCleaning, const ['Home deep cleaning', 'Bathroom cleaning', 'Sofa cleaning']),
  ServiceType('domestic_help', Icons.house_outlined, ServiceGroup.homeHelp, (l) => l.typeDomesticHelp, const ['House help', 'Utensil and floor cleaning']),
  ServiceType('cook', Icons.soup_kitchen_outlined, ServiceGroup.homeHelp, (l) => l.typeCook, const ['Home cook', 'Cook for a party']),
  ServiceType('care_giver', Icons.elderly, ServiceGroup.homeHelp, (l) => l.typeCareGiver, const ['Elder care', 'Baby care']),
  ServiceType('laundry', Icons.local_laundry_service, ServiceGroup.homeHelp, (l) => l.typeLaundry, const ['Wash and iron', 'Dry cleaning', 'Ironing']),
  ServiceType('gardening', Icons.yard_outlined, ServiceGroup.homeHelp, (l) => l.typeGardening, const ['Garden care', 'Plant care']),
  ServiceType('packers_movers', Icons.local_shipping_outlined, ServiceGroup.homeHelp, (l) => l.typePackersMovers, const ['House shifting', 'Goods transport']),
  ServiceType('vehicle_repair', Icons.car_repair, ServiceGroup.vehicles, (l) => l.categoryVehicleRepair, const ['Car service', 'Bike service', 'Puncture repair', 'Battery change']),
  ServiceType('car_wash', Icons.local_car_wash, ServiceGroup.vehicles, (l) => l.typeCarWash, const ['Car wash', 'Bike wash', 'Interior cleaning']),
  ServiceType('driver', Icons.drive_eta_outlined, ServiceGroup.vehicles, (l) => l.typeDriver, const ['Driver for the day', 'Driver for a trip']),
  ServiceType('electronics_repair', Icons.devices, ServiceGroup.other, (l) => l.categoryElectronicsRepair, const ['Screen replacement', 'Battery replacement', 'Laptop repair', 'CCTV installation']),
  ServiceType('tutor', Icons.school_outlined, ServiceGroup.learning, (l) => l.typeTutor, const ['Home tuition', 'Maths tuition', 'Spoken English']),
  ServiceType('fitness', Icons.fitness_center, ServiceGroup.learning, (l) => l.typeFitness, const ['Yoga class', 'Personal trainer', 'Zumba class']),
  ServiceType('music_dance', Icons.music_note_outlined, ServiceGroup.learning, (l) => l.typeMusicDance, const ['Music class', 'Dance class']),
  ServiceType('photography', Icons.photo_camera_outlined, ServiceGroup.events, (l) => l.typePhotography, const ['Wedding photography', 'Event photography', 'Photo session']),
  ServiceType('catering', Icons.restaurant_outlined, ServiceGroup.events, (l) => l.typeCatering, const ['Party catering', 'Wedding catering']),
  ServiceType('event_decor', Icons.celebration_outlined, ServiceGroup.events, (l) => l.typeEventDecor, const ['Birthday decoration', 'Wedding decoration', 'Tent and lighting']),
  ServiceType('priest', Icons.temple_hindu_outlined, ServiceGroup.events, (l) => l.typePriest, const ['Griha pravesh puja', 'Wedding ceremony', 'Puja at home']),
  ServiceType('tax_legal', Icons.gavel_outlined, ServiceGroup.other, (l) => l.typeTaxLegal, const ['ITR filing', 'GST registration', 'Legal consultation']),
  ServiceType('office', Icons.event_available, ServiceGroup.other, (l) => l.categoryOffice, const ['Appointment']),
  ServiceType('other', Icons.more_horiz, ServiceGroup.other, (l) => l.categoryOther, const []),
];

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
