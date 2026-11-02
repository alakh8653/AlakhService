import '../../../l10n/l10n.dart';

/// Kinds of business customers book with; the same values as the shop dashboard's categories.
const businessCategories = [
  'salon',
  'beauty',
  'spa',
  'clinic',
  'vehicle_repair',
  'electronics_repair',
  'appliance_repair',
  'cleaning',
  'plumbing',
  'electrical',
  'repair',
  'office',
  'other',
];

String businessCategoryLabel(String category, AppLocalizations l10n) => switch (category) {
      'salon' => l10n.categorySalon,
      'beauty' => l10n.categoryBeauty,
      'spa' => l10n.categorySpa,
      'clinic' => l10n.categoryClinic,
      'vehicle_repair' => l10n.categoryVehicleRepair,
      'electronics_repair' => l10n.categoryElectronicsRepair,
      'appliance_repair' => l10n.categoryApplianceRepair,
      'cleaning' => l10n.categoryCleaning,
      'plumbing' => l10n.categoryPlumbing,
      'electrical' => l10n.categoryElectrical,
      'repair' => l10n.categoryRepair,
      'office' => l10n.categoryOffice,
      _ => l10n.categoryOther,
    };
