/* eslint-disable @next/next/no-img-element */
'use client';

import React from 'react';
import { Edit2, Trash2, Package, Layers } from 'lucide-react';
import { Product } from '@/types/product';
import { Button } from '@/components/ui/button';

interface ProductCardProps {
  product: Product;
  onEdit: (product: Product) => void;
  onDelete: (id: string) => void;
  isDeleting: boolean;
}

export const ProductCard = ({ product, onEdit, onDelete, isDeleting }: ProductCardProps) => {
  const formattedPrice = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: product.currency,
  }).format(product.price / 100);

  const getStockColor = (stock: number) => {
    if (stock <= 0) return 'bg-rose-50 text-rose-700 border-rose-100';
    if (stock <= 5) return 'bg-amber-50 text-amber-700 border-amber-100';
    return 'bg-emerald-50 text-emerald-700 border-emerald-100';
  };

  const getStockText = (stock: number) => {
    if (stock <= 0) return 'Out of Stock';
    if (stock <= 5) return `Low Stock (${stock})`;
    return `In Stock (${stock})`;
  };

  return (
    <div className="bg-white/80 backdrop-blur-md border border-indigo-100/50 rounded-2xl p-5 shadow-sm hover:shadow-md hover:border-indigo-200/50 transition-all flex flex-col justify-between h-full group relative overflow-hidden">
      {/* Background Micro-animation */}
      <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-50/30 rounded-full blur-2xl group-hover:bg-indigo-100/40 transition-colors duration-300 -mr-8 -mt-8" />
      
      <div>
        {/* Header - Image or Icon Placeholder */}
        <div className="h-48 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center mb-4 overflow-hidden relative">
          {product.image ? (
            <img 
              src={product.image} 
              alt={product.name} 
              className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
          ) : (
            <Package className="w-12 h-12 text-slate-300 group-hover:text-indigo-400 transition-colors duration-300" />
          )}
          
          {/* Status badge */}
          <div className="absolute top-3 left-3 flex gap-2">
            <span className={`px-2 py-0.5 rounded-full border text-[10px] font-extrabold uppercase tracking-wide shadow-sm ${getStockColor(product.stock)}`}>
              {getStockText(product.stock)}
            </span>
            {!product.is_active && (
              <span className="px-2 py-0.5 rounded-full border border-slate-200 bg-slate-100 text-slate-600 text-[10px] font-extrabold uppercase tracking-wide">
                Inactive
              </span>
            )}
          </div>
        </div>

        {/* Info */}
        <div className="space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono text-slate-400 font-semibold tracking-wider flex items-center gap-1">
              <Layers className="w-3 h-3" />
              {product.sku || 'NO SKU'}
            </span>
            <span className="text-sm font-extrabold text-indigo-600">{formattedPrice}</span>
          </div>
          <h4 className="text-sm font-bold text-slate-800 line-clamp-1 group-hover:text-indigo-600 transition-colors">
            {product.name}
          </h4>
          <p className="text-xs text-slate-400 font-medium line-clamp-2 min-h-[2rem]">
            {product.description || 'No description provided.'}
          </p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 mt-4 pt-4 border-t border-slate-50 relative z-10">
        <Button 
          variant="outline"
          size="sm"
          onClick={() => onEdit(product)}
          className="flex-1 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 border-slate-200 text-xs font-semibold cursor-pointer h-9 gap-1.5"
        >
          <Edit2 className="w-3.5 h-3.5" />
          Edit
        </Button>
        <Button 
          variant="outline"
          size="sm"
          disabled={isDeleting}
          onClick={() => onDelete(product.id)}
          className="text-slate-400 hover:text-rose-600 hover:bg-rose-50 border-slate-200 hover:border-rose-100 h-9 px-3 cursor-pointer"
        >
          <Trash2 className="w-3.5 h-3.5" />
        </Button>
      </div>
    </div>
  );
};
