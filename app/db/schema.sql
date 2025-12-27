CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TYPE public.category AS ENUM ('mobile', 'bank');

CREATE TYPE public.transaction_type AS ENUM (
  'deposit',
  'withdrawal',
  'airtime',
  'bundle',
  'electricity',
  'water',
  'tv',
  'other_utility',
  'bank_deposit',
  'bank_withdrawal',
  'bill_payment',
  'funds_transfer',
  'account_to_wallet',
  'wallet_to_account'
);

CREATE TYPE public.float_operation_type AS ENUM ('top_up', 'withdraw');

CREATE TYPE public.app_role AS ENUM ('superadmin', 'cashier');

CREATE TYPE public.audit_action AS ENUM (
  'create',
  'update',
  'delete',
  'login',
  'logout',
  'float_top_up',
  'float_withdraw',
  'import',
  'export',
  'settings_change'
);

-- USERS
CREATE TABLE public.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username text UNIQUE NOT NULL,
  email text UNIQUE NOT NULL,
  phone text,
  full_name text NOT NULL,
  hashed_password text NOT NULL,
  is_active boolean DEFAULT true NOT NULL,
  role app_role NOT NULL DEFAULT 'superadmin',
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  deleted_at timestamptz
);

-- REFRESH TOKENS
CREATE TABLE public.refresh_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
    token text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    revoked boolean DEFAULT false NOT NULL
);

-- PROFILES
CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES public.users(id) ON DELETE CASCADE,
  avatar_url text,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- USER ROLES
CREATE TABLE public.user_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  role app_role NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  UNIQUE (user_id, role)
);

-- SHOPS
CREATE TABLE public.shops (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  location text NOT NULL,
  owner_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- CASHIERS
CREATE TABLE public.cashiers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
  is_active boolean DEFAULT true NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL,
  UNIQUE (user_id, shop_id)
);

-- PROVIDERS
CREATE TABLE public.providers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
  name text NOT NULL,
  category public.category NOT NULL,
  agent_code text,
  opening_balance numeric(15,2) DEFAULT 0 NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- SUPER AGENTS
CREATE TABLE public.super_agents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
  name text NOT NULL,
  reference text NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- TRANSACTIONS
CREATE TABLE public.transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
  provider_id uuid REFERENCES public.providers(id) ON DELETE RESTRICT NOT NULL,
  recorded_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  category public.category NOT NULL,
  type public.transaction_type NOT NULL,
  amount numeric(15,2) NOT NULL CHECK (amount >= 0),
  commission numeric(15,2) DEFAULT 0 NOT NULL CHECK (commission >= 0),
  reference text NOT NULL,
  customer_identifier text NOT NULL,
  receipt_image_url text,
  notes text,
  transaction_date timestamptz NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- FLOAT MOVEMENTS
CREATE TABLE public.float_movements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
  provider_id uuid REFERENCES public.providers(id) ON DELETE RESTRICT NOT NULL,
  super_agent_id uuid REFERENCES public.super_agents(id) ON DELETE RESTRICT NOT NULL,
  recorded_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
  type public.float_operation_type NOT NULL,
  category public.category NOT NULL,
  amount numeric(15,2) NOT NULL CHECK (amount > 0),
  reference text NOT NULL,
  is_new_capital boolean DEFAULT false NOT NULL,
  receipt_image_url text,
  notes text,
  transaction_date timestamptz NOT NULL,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- FLOAT BALANCES
CREATE TABLE public.float_balances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL,
  provider_id uuid REFERENCES public.providers(id) ON DELETE CASCADE NOT NULL,
  category public.category NOT NULL,
  balance numeric(15,2) DEFAULT 0 NOT NULL,
  last_updated timestamptz DEFAULT now() NOT NULL,
  UNIQUE (shop_id, provider_id, category)
);

-- CASH BALANCES
CREATE TABLE public.cash_balances (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id uuid REFERENCES public.shops(id) ON DELETE CASCADE NOT NULL UNIQUE,
  balance numeric(15,2) DEFAULT 0 NOT NULL,
  opening_balance numeric(15,2) DEFAULT 0 NOT NULL,
  last_updated timestamptz DEFAULT now() NOT NULL
);

-- AUDIT LOGS
CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  shop_id uuid REFERENCES public.shops(id) ON DELETE SET NULL,
  user_id uuid REFERENCES public.users(id) ON DELETE SET NULL,
  action public.audit_action NOT NULL,
  entity_type text,
  entity_id uuid,
  details jsonb,
  ip_address inet,
  user_agent text,
  created_at timestamptz DEFAULT now() NOT NULL
);

-- USER SETTINGS
CREATE TABLE public.user_settings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES public.users(id) ON DELETE CASCADE NOT NULL UNIQUE,
  currency_name text DEFAULT 'Tanzanian Shilling' NOT NULL,
  currency_code text DEFAULT 'TZS' NOT NULL,
  theme text DEFAULT 'system',
  preferences jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now() NOT NULL,
  updated_at timestamptz DEFAULT now() NOT NULL
);

-- INDEXES
CREATE INDEX idx_transactions_shop_id ON public.transactions(shop_id);
CREATE INDEX idx_transactions_provider_id ON public.transactions(provider_id);
CREATE INDEX idx_transactions_recorded_by ON public.transactions(recorded_by);
CREATE INDEX idx_transactions_transaction_date ON public.transactions(transaction_date);
CREATE INDEX idx_transactions_category ON public.transactions(category);
CREATE INDEX idx_transactions_type ON public.transactions(type);

CREATE INDEX idx_float_movements_shop_id ON public.float_movements(shop_id);
CREATE INDEX idx_float_movements_provider_id ON public.float_movements(provider_id);
CREATE INDEX idx_float_movements_transaction_date ON public.float_movements(transaction_date);

CREATE INDEX idx_float_balances_shop_id ON public.float_balances(shop_id);
CREATE INDEX idx_float_balances_provider_id ON public.float_balances(provider_id);

CREATE INDEX idx_cashiers_shop_id ON public.cashiers(shop_id);
CREATE INDEX idx_cashiers_user_id ON public.cashiers(user_id);

CREATE INDEX idx_providers_shop_id ON public.providers(shop_id);
CREATE INDEX idx_providers_category ON public.providers(category);

CREATE INDEX idx_super_agents_shop_id ON public.super_agents(shop_id);

CREATE INDEX idx_audit_logs_shop_id ON public.audit_logs(shop_id);
CREATE INDEX idx_audit_logs_user_id ON public.audit_logs(user_id);
CREATE INDEX idx_audit_logs_created_at ON public.audit_logs(created_at);
CREATE INDEX idx_audit_logs_action ON public.audit_logs(action);
