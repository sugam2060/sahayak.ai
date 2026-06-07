/* eslint-disable @next/next/no-img-element */
'use client';

import React, { useState } from 'react';
import { Package, Check } from 'lucide-react';
import { useProducts } from '@/services/api/products';
import { Product } from '@/types/product';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

interface ProductShareModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (products: Product[]) => void;
}

export const ProductShareModal = ({ open, onOpenChange, onSelect }: ProductShareModalProps) => {
  const [search, setSearch] = useState('');
  const [stockStatus, setStockStatus] = useState<'all' | 'in_stock' | 'out_of_stock'>('all');
  const [isActive, setIsActive] = useState<'all' | 'active' | 'inactive'>('all');
  const [selectedProducts, setSelectedProducts] = useState<Product[]>([]);

  const { data: productsData } = useProducts({
    limit: 100,
    search: search || undefined,
    stock_status: stockStatus === 'all' ? undefined : stockStatus,
    is_active: isActive === 'all' ? undefined : (isActive === 'active')
  });

  const products = productsData?.products || [];

  const handleToggleSelect = (p: Product) => {
    const isSelected = selectedProducts.some((item) => item.id === p.id);
    if (isSelected) {
      setSelectedProducts(selectedProducts.filter((item) => item.id !== p.id));
    } else {
      setSelectedProducts([...selectedProducts, p]);
    }
  };

  const handleShareClick = () => {
    if (selectedProducts.length > 0) {
      onSelect(selectedProducts);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px] bg-white p-6 rounded-2xl border border-indigo-50 shadow-2xl flex flex-col max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="text-base font-bold text-slate-800">Select Products to Share</DialogTitle>
          <DialogDescription className="sr-only">
            Select one or more products to share in the chat.
          </DialogDescription>
        </DialogHeader>

        {/* Search Input */}
        <div className="mt-2">
          <input 
            type="text" 
            placeholder="Search product by name, description or SKU..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full px-3 py-2 bg-slate-50 border border-slate-200 focus:border-indigo-500 rounded-xl text-xs focus:outline-none"
          />
        </div>

        {/* Filters Dropdowns */}
        <div className="flex gap-3">
          <select 
            value={stockStatus}
            onChange={(e) => setStockStatus(e.target.value as 'all' | 'in_stock' | 'out_of_stock')}
            className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-2 py-1.5 text-[10px] font-bold text-slate-500 cursor-pointer focus:outline-none"
          >
            <option value="all">All Stocks</option>
            <option value="in_stock">In Stock</option>
            <option value="out_of_stock">Out of Stock</option>
          </select>

          <select 
            value={isActive}
            onChange={(e) => setIsActive(e.target.value as 'all' | 'active' | 'inactive')}
            className="flex-1 bg-slate-50 border border-slate-200 rounded-xl px-2 py-1.5 text-[10px] font-bold text-slate-500 cursor-pointer focus:outline-none"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>

        {/* Products List */}
        <div className="flex-1 overflow-y-auto space-y-2 pr-1 my-2 min-h-[150px] max-h-[300px]">
          {products.map((p) => {
            const isSelected = selectedProducts.some((item) => item.id === p.id);
            return (
              <div 
                key={p.id} 
                onClick={() => handleToggleSelect(p)}
                className={`flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer select-none
                  ${isSelected 
                    ? 'border-indigo-200 bg-indigo-50/30' 
                    : 'border-slate-100 hover:border-indigo-100 hover:bg-indigo-50/10'}`}
              >
                {/* Custom circular/rounded checkbox */}
                <div className={`w-5 h-5 rounded-md border flex items-center justify-center transition-all flex-shrink-0
                  ${isSelected 
                    ? 'bg-indigo-600 border-indigo-600 text-white' 
                    : 'border-slate-300 bg-white'}`}
                >
                  {isSelected && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                </div>

                <div className="w-12 h-12 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center overflow-hidden flex-shrink-0">
                  {p.image ? (
                    <img src={p.image} alt={p.name} className="w-full h-full object-cover" />
                  ) : (
                    <Package className="w-6 h-6 text-slate-300" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="text-xs font-bold text-slate-800 truncate">{p.name}</div>
                  <div className="text-[10px] font-mono text-slate-400 mt-0.5">{p.sku || 'No SKU'}</div>
                </div>

                <div className="text-right">
                  <div className="text-xs font-bold text-indigo-600">
                    {new Intl.NumberFormat('en-US', { style: 'currency', currency: p.currency }).format(p.price)}
                  </div>
                  <div className="text-[9px] text-slate-400 mt-0.5">Stock: {p.stock}</div>
                </div>
              </div>
            );
          })}
          {products.length === 0 && (
            <div className="text-center py-8 text-xs text-slate-400">No products found.</div>
          )}
        </div>

        {/* Action Footer */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-100 flex-shrink-0">
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="px-4 py-2 text-xs font-bold text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded-xl transition-all cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={selectedProducts.length === 0}
            onClick={handleShareClick}
            className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl shadow-md shadow-indigo-100 active:scale-[0.98] transition-all cursor-pointer"
          >
            Share Selected ({selectedProducts.length})
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
