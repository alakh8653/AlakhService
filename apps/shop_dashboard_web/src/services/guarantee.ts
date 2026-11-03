import { z } from 'zod';

/** The free-fix guarantee a shop starts with (shop_service's default), and the longest it may offer. */
export const DEFAULT_GUARANTEE_DAYS = 7;
export const MAX_GUARANTEE_DAYS = 90;

/** "Free-fix guarantee (days)" as typed into a number box: a whole number from 0 to 90. */
export const guaranteeDaysField = z
  .string()
  .trim()
  .refine((v) => /^\d+$/.test(v) && Number(v) <= MAX_GUARANTEE_DAYS, `A whole number of days from 0 to ${MAX_GUARANTEE_DAYS}`);

export const GUARANTEE_HELP =
  'If something goes wrong after a job, the customer can ask for a free fix within these days. 0 means no guarantee.';
