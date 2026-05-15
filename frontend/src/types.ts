// Mirror of backend/app/schemas.py — изменился бэк, не забыть здесь.

export type UserRole = "buyer" | "seller" | "admin";

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  role_label: string;
}

export type ProductStatus = "pending" | "published" | "rejected";

export interface Product {
  id: number;
  name: string;
  description: string;
  price: string;
  sizes: string[];
  stock: Record<string, number>;
  image_url: string | null;
  status: ProductStatus;
  status_label: string;
  rejection_reason: string | null;
  seller_username: string | null;
  seller_id: number | null;
  created_at: string;
  updated_at: string;
}

export interface CartItem {
  id: number;
  product: Product;
  size: string;
  quantity: number;
  line_total: string;
}

export interface Cart {
  items: CartItem[];
  total: string;
  item_count: number;
}

export type OrderStatus = "created" | "paid" | "cancelled";
export type DeliveryStatus = "processing" | "shipped" | "in_transit" | "delivered";

export interface OrderItem {
  id: number;
  product_id: number | null;
  product_name: string;
  product_price: string;
  sizes: string[];
  quantity: number;
  line_total: string;
}

export interface Receipt {
  receipt_number: string;
  transaction_id: string;
  pdf_url: string;
  issued_at: string;
}

export interface Order {
  id: number;
  status: OrderStatus;
  status_label: string;
  total: string;
  recipient_name: string;
  recipient_phone: string;
  delivery_address: string;
  comment: string;
  created_at: string;
  paid_at: string | null;
  items: OrderItem[];
  receipt: Receipt | null;
  delivery_status: DeliveryStatus;
  delivery_status_label: string;
  delivery_visible: boolean;
  delivery_updated_at: string | null;
  shipped_at: string | null;
  delivered_at: string | null;
  buyer_id: number;
  buyer_username: string | null;
  buyer_email: string | null;
}

export interface AdminCounts {
  pending: number;
  published: number;
  rejected: number;
  total_users: number;
}

export interface EnumValue {
  value: string;
  label: string;
}

export interface Enums {
  delivery_statuses: EnumValue[];
  delivery_status_order: DeliveryStatus[];
  order_statuses: EnumValue[];
  product_statuses: EnumValue[];
  user_roles: EnumValue[];
}

export interface SellerDashboard {
  counts: Record<ProductStatus, number>;
  recent: Product[];
}
