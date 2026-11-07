---
name: Culinary Atelier
colors:
  surface: '#fff8f6'
  surface-dim: '#e4d7d4'
  surface-bright: '#fff8f6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#fef1ed'
  surface-container: '#f8ebe7'
  surface-container-high: '#f2e5e2'
  surface-container-highest: '#ece0dc'
  on-surface: '#201a18'
  on-surface-variant: '#57423c'
  inverse-surface: '#362f2d'
  inverse-on-surface: '#fbeeea'
  outline: '#8a726b'
  outline-variant: '#dec0b8'
  surface-tint: '#a23f1d'
  primary: '#7e2505'
  on-primary: '#ffffff'
  primary-container: '#9e3c1b'
  on-primary-container: '#ffc8b7'
  inverse-primary: '#ffb59e'
  secondary: '#396752'
  on-secondary: '#ffffff'
  secondary-container: '#b9ebcf'
  on-secondary-container: '#3e6c56'
  tertiary: '#6c3600'
  on-tertiary: '#ffffff'
  tertiary-container: '#8f4900'
  on-tertiary-container: '#ffcaa4'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbd0'
  primary-fixed-dim: '#ffb59e'
  on-primary-fixed: '#3a0b00'
  on-primary-fixed-variant: '#822807'
  secondary-fixed: '#bceed2'
  secondary-fixed-dim: '#a0d1b7'
  on-secondary-fixed: '#002114'
  on-secondary-fixed-variant: '#214f3b'
  tertiary-fixed: '#ffdcc4'
  tertiary-fixed-dim: '#ffb781'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#703800'
  background: '#fff8f6'
  on-background: '#201a18'
  surface-variant: '#ece0dc'
typography:
  display-lg:
    fontFamily: Outfit
    fontSize: 48px
    fontWeight: '600'
    lineHeight: 56px
    letterSpacing: -0.02em
  display-lg-mobile:
    fontFamily: Outfit
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Outfit
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-lg-mobile:
    fontFamily: Outfit
    fontSize: 26px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Outfit
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Outfit
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  title-md:
    fontFamily: Outfit
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.01em
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.5rem
  gutter-mobile: 1rem
  margin: 2rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system embodies an artisanal yet highly structured culinary SaaS identity, balancing the raw sensory warmth of professional gastronomy with the clarity, efficiency, and rigor of modern kitchen operations. Designed for chefs, restaurant operators, and culinary entrepreneurs, the aesthetic avoids clinical tech tropes in favor of an organic, earthy sophistication.

Drawing from warm minimalism and editorial tactile design, the interface pairs deep earth-baked hues with warm off-white canvases. The visual mood delivers an emotional payoff of grounded expertise, culinary focus, and premium precision. Surfaces feel like artisan paper and honed stone rather than flat digital sheets, while interface feedback is immediate, quiet, and deliberate.

## Colors

The color palette grounds the UI in authentic culinary materials: terracotta ceramics, fresh botanical herbs, and rich spices.

- **Primary (`#9E3C1B`)**: Terracotta serves as the focal point for core conversion moments, primary action buttons, active toggles, and high-priority states.
- **Secondary (`#2F5D48`)**: Deep botanical green provides grounding for persistent navigation chrome, sidebars, active tabs, and validation/certified states.
- **Tertiary (`#B4651E`)**: Ocher acts as an accent tone for pending statuses, warm highlights, tags, and secondary operational callouts.
- **Neutral (`#201A18`)**: Deep espresso brown replaces cold synthetic blacks, offering high contrast with a warm, natural density for typography and structural icons.
- **Surfaces & Backgrounds**: Layered in subtle warm neutrals: `#FAF7F4` (canvas), `#F5EFEB` (card surface / container low), and `#EDE6E0` (container high / elevated inputs and borders).

## Typography

The typographic hierarchy pairs the architectural, geometric flair of Outfit with the neutral clarity of Inter.

- **Headlines (Outfit)**: Used for high-impact metrics, section titling, modal headers, and page anchors. Outfit lends a polished, high-end editorial voice to restaurant menus and operational metrics.
- **Body & Labels (Inter)**: Employs a dense, clean grotesque structure optimized for dense tabular recipe data, ingredient bills, inventory lists, and form controls. Micro-letterspacing is widened slightly for all-caps badges and tabular captions to ensure legibility in kitchen light conditions.

## Layout & Spacing

The layout is structured around an 8px base rhythm arranged in a fluid 12-column responsive grid for desktop and tablet, collapsing to a single-column or 2-column stack on mobile.

- **Desktop (>= 1280px)**: 12 columns, 24px gutters (`1.5rem`), and 32px margins (`2rem`). The primary sidebar locks at a fixed 280px width styled in deep botanical green (`#2F5D48`), with operational panels using fluid multi-column splits.
- **Tablet (768px - 1279px)**: 8 columns, 16px gutters, and 24px margins. The sidebar collapses into an icon rail or off-canvas drawer.
- **Mobile (< 768px)**: 4 columns, 16px gutters (`gutter-mobile`), and 16px margins (`margin-mobile`). Forms, cards, and data summaries expand edge-to-edge within the content canvas.

## Elevation & Depth

Visual depth is achieved through organic tonal layering rather than heavy artificial drop shadows.

- **Tonal Stepping**: The application canvas rests on warm sand (`#FAF7F4`). Cards, recipe containers, and content blocks sit slightly elevated on clean linen (`#F5EFEB`). Floating layers, active popovers, and dialogs sit on pure warm white (`#FFFFFF`) with borders tinted in `#EDE6E0`.
- **Shadow Profile**: Where elevation is required (dropdowns, flyout sheets, modals), shadows are ultra-diffused, using warm espresso undertones rather than cold grays: `0 8px 24px -4px rgba(32, 26, 24, 0.08), 0 2px 6px -1px rgba(32, 26, 24, 0.04)`.
- **Dividers & Structural Rules**: Subtle, low-contrast 1px solid lines using `#EDE6E0` delineate table rows, recipe steps, and header boundaries without fragmenting the canvas.

## Shapes

The interface embraces a balanced, friendly geometry with a roundedness factor of 2.

- Standard buttons, badges, and input controls use `0.5rem` (8px) corner radii.
- Content cards, modals, and panel wrappers utilize `rounded-lg` (`1rem` / 16px) or `rounded-xl` (`1.5rem` / 24px) to soften analytical SaaS layouts and echo the curved lines of ceramic tableware.
- Status pills, avatars, and counter chips utilize fully rounded circular caps.

## Components

- **Buttons**:
  - *Primary*: Filled Terracotta (`#9E3C1B`) with crisp warm off-white (`#FAF7F4`) text. Hover introduces a subtle darkening (`#873316`), and focus renders a dual ring: 2px offset in `#FAF7F4` and 2px stroke in `#9E3C1B`.
  - *Secondary*: Deep botanical green outline (`#2F5D48`) or muted neutral wash (`#EDE6E0`) with deep espresso text (`#201A18`).
  - *Tertiary/Ghost*: Transparent background with Terracotta or Green text for inline actions.

- **Inputs & Form Controls**:
  - Base field uses `#FFFFFF` or `#FAF7F4` fill with a 1px border in `#EDE6E0` and text in `#201A18`.
  - Focus state elevates with a 1.5px border in Terracotta (`#9E3C1B`) accompanied by a soft 3px aura (`rgba(158, 60, 27, 0.15)`).
  - Validation errors trigger a brick-red outline, while verified/saved fields transition borders to deep green (`#2F5D48`).

- **Cards & Data Containers**:
  - Structured with `#F5EFEB` background, `1rem` corner rounding, and a 1px border in `#EDE6E0`.
  - Card headers feature Outfit Medium typography with optional ocher (`#B4651E`) tag highlights.

- **Chips & Badges**:
  - *Certified / Approved*: Botanical green fill at 10% opacity with solid `#2F5D48` text and icon.
  - *Pending / Caution*: Ocher fill at 12% opacity with solid `#B4651E` text.
  - *Ingredient / Categorical*: Warm espresso neutral fill at 6% opacity with `#201A18` text.

- **Lists & Tables**:
  - Recipe steps, inventory rows, and order manifests feature alternating soft off-white surface fills, separated by 1px `#EDE6E0` borders, with row hover subtly transitioning to `#EDE6E0`.
  - Drag-and-drop culinary reordering highlights target dropzones with a dashed `#9E3C1B` indicator.

- **Specialized Culinary SaaS Elements**:
  - *Yield & Portion Calculators*: Numeric step controls with Terracotta icon buttons and Inter mono-aligned numeric readouts.
  - *Status Banners*: Soft cream base with left-border accents in Terracotta (urgent prep), Deep Green (station ready), or Ocher (low stock).