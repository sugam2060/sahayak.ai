/* eslint-disable @next/next/no-img-element */
'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { FaBoxOpen, FaTags, FaInfoCircle } from 'react-icons/fa';
import { MdOutlineVerified, MdOutlineCrisisAlert } from 'react-icons/md';
import { FiShoppingBag } from 'react-icons/fi';

interface ProductMetadata {
  brand?: string;
  color?: string;
  model?: string;
  category?: string;
  keywords?: string[];
}

interface Product {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  price: number; // in cents/subunits
  currency: string;
  stock: number;
  sku: string | null;
  image: string | null;
  is_active: boolean;
  metadata?: ProductMetadata | null;
  created_at: string;
  updated_at: string;
}

interface SharedProductDetailProps {
  product: Product;
}

export const SharedProductDetail = ({ product }: SharedProductDetailProps) => {
  const currencyUpper = (product.currency || 'NPR').toUpperCase();
  const symbolMap: Record<string, string> = {
    USD: '$', EUR: '€', GBP: '£', INR: '₹',
    CAD: 'CA$', AUD: 'A$', JPY: '¥'
  };
  const symbol = symbolMap[currencyUpper] || `${currencyUpper} `;
  
  // Format price (cents to units)
  const formattedPrice = (product.price / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });

  const isOutOfStock = product.stock <= 0;
  const metadata = product.metadata as Record<string, unknown> | null | undefined;
  const hasSpecs = metadata && Object.keys(metadata).some(k => k.toLowerCase() !== 'keywords' && metadata[k]);

  return (
    <div className="max-w-7xl mx-auto w-full relative z-10">
      <Card className="bg-white/80 dark:bg-zinc-900/80 backdrop-blur-md border border-slate-100 dark:border-zinc-800 shadow-2xl overflow-hidden rounded-[32px]">
        <CardContent className="p-0">
          <div className="grid grid-cols-1 lg:grid-cols-12 items-stretch min-h-[70vh]">
            
            {/* Product Image Section */}
            <div className="lg:col-span-6 p-8 lg:p-12 bg-slate-50/50 dark:bg-zinc-950/20 flex flex-col justify-center items-center border-b lg:border-b-0 lg:border-r border-slate-100 dark:border-zinc-800">
              {product.image ? (
                <div className="w-full aspect-square max-w-[600px] rounded-3xl overflow-hidden shadow-lg bg-white dark:bg-zinc-850 border border-slate-100 dark:border-zinc-700 flex items-center justify-center p-6 relative group transition-all duration-300 hover:shadow-xl">
                  <img
                    src={product.image}
                    alt={product.name}
                    className="max-w-full max-h-full object-contain transition-transform duration-500 group-hover:scale-105"
                  />
                </div>
              ) : (
                <div className="w-full aspect-square max-w-[600px] rounded-3xl bg-white dark:bg-zinc-850 border border-slate-100 dark:border-zinc-800 flex flex-col items-center justify-center text-slate-400 gap-3 shadow-inner">
                  <FiShoppingBag className="w-16 h-16 stroke-[1.5]" />
                  <span className="text-xs font-semibold tracking-wider">NO IMAGE AVAILABLE</span>
                </div>
              )}
            </div>

            {/* Product Details Section */}
            <div className="lg:col-span-6 p-8 sm:p-12 lg:p-16 flex flex-col justify-between">
              <div>
                {/* Active / Stock Badge */}
                <div className="flex items-center gap-3 mb-8">
                  {isOutOfStock ? (
                    <span className="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-bold bg-amber-50 dark:bg-amber-950/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-900/30">
                      <MdOutlineCrisisAlert className="w-4 h-4 mr-1.5" /> Out of Stock
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-bold bg-emerald-50 dark:bg-emerald-950/20 text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-900/30">
                      <MdOutlineVerified className="w-4 h-4 mr-1.5" /> In Stock
                    </span>
                  )}
                  {product.sku && (
                    <span className="inline-flex items-center px-4 py-1.5 rounded-full text-xs font-semibold bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700/50">
                      SKU: {product.sku}
                    </span>
                  )}
                </div>

                {/* Title & Price */}
                <h1 className="text-3xl sm:text-4xl lg:text-5xl font-black text-slate-800 dark:text-zinc-100 tracking-tight leading-tight mb-6">
                  {product.name}
                </h1>
                
                <div className="text-4xl lg:text-5xl font-black text-indigo-600 dark:text-indigo-400 tracking-tight mb-8">
                  {symbol}{formattedPrice}
                </div>

                {/* Description */}
                <div className="border-t border-slate-100 dark:border-zinc-800 pt-8 mb-8">
                  <h3 className="text-xs font-bold tracking-widest text-slate-400 dark:text-zinc-500 uppercase mb-4 flex items-center gap-1.5">
                    <FaInfoCircle className="w-3.5 h-3.5 text-slate-400" /> Description
                  </h3>
                  <p className="text-slate-600 dark:text-zinc-300 text-base leading-relaxed whitespace-pre-line font-medium">
                    {product.description || 'No description provided for this product.'}
                  </p>
                </div>

                {/* Specifications / Metadata */}
                {hasSpecs && (
                  <div className="border-t border-slate-100 dark:border-zinc-800 pt-8">
                    <h3 className="text-xs font-bold tracking-widest text-slate-400 dark:text-zinc-500 uppercase mb-4 flex items-center gap-1.5">
                      <FaTags className="w-3.5 h-3.5 text-slate-400" /> Specifications
                    </h3>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                      {Object.entries(metadata).map(([key, value]) => {
                        if (key.toLowerCase() === 'keywords' || !value) return null;
                        return (
                          <div key={key} className="bg-slate-50/50 dark:bg-zinc-900/50 border border-slate-100/30 dark:border-zinc-800/30 rounded-xl p-4 flex flex-col">
                            <span className="text-[10px] font-bold text-slate-400 dark:text-zinc-500 uppercase tracking-wider mb-1.5">{key}</span>
                            <span className="text-sm font-semibold text-slate-700 dark:text-zinc-200">
                              {Array.isArray(value) ? value.join(', ') : String(value)}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-12 pt-8 border-t border-slate-100 dark:border-zinc-800 text-center text-[10px] font-bold text-slate-400 dark:text-zinc-500 tracking-widest flex items-center justify-center gap-1.5">
                <FaBoxOpen className="w-4 h-4" /> POWERED BY SAHAYAK AI
              </div>

            </div>

          </div>
        </CardContent>
      </Card>
    </div>
  );
};
