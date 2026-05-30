'use client';

import React from 'react';
import { Edit2, Trash2, Package } from 'lucide-react';
import { Product } from '@/types/product';
import { Button } from '@/components/ui/button';

interface ProductTableProps {
  products: Product[];
  onEdit: (product: Product) => void;
  onDelete: (id: string) => void;
  isDeleting: boolean;
}

export const ProductTable = ({ products, onEdit, onDelete, isDeleting }: ProductTableProps) => {
  const formatPrice = (price: number, currency: string) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency,
    }).format(price / 100);
  };

  const getStockColor = (stock: number) => {
    if (stock <= 0) return 'bg-rose-50 text-rose-700 border-rose-100';
    if (stock <= 5) return 'bg-amber-50 text-amber-700 border-amber-100';
    return 'bg-emerald-50 text-emerald-700 border-emerald-100';
  };

  const getStockText = (stock: number) => {
    if (stock <= 0) return 'Out of stock';
    if (stock <= 5) return `Low Stock (${stock})`;
    return `In Stock (${stock})`;
  };

  return (
    <div className="w-full overflow-hidden bg-white/80 backdrop-blur-md rounded-2xl border border-indigo-100/50 shadow-sm">
      <div className="w-full overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-indigo-50/50 bg-slate-50/50 text-[10px] uppercase font-bold text-slate-400 tracking-wider">
              <th className="py-4 px-6">Product</th>
              <th className="py-4 px-6">SKU</th>
              <th className="py-4 px-6">Price</th>
              <th className="py-4 px-6">Stock</th>
              <th className="py-4 px-6">Status</th>
              <th className="py-4 px-6 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-indigo-50/20">
            {products.map((product) => (
              <tr key={product.id} className="hover:bg-slate-50/30 transition-colors text-slate-700 text-xs font-semibold">
                <td className="py-4 px-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center overflow-hidden flex-shrink-0">
                      {product.image ? (
                        <img src={product.image} alt={product.name} className="w-full h-full object-cover" />
                      ) : (
                        <Package className="w-5 h-5 text-slate-300" />
                      )}
                    </div>
                    <div>
                      <div className="text-slate-800 font-bold hover:text-indigo-600 transition-colors cursor-pointer">{product.name}</div>
                      <div className="text-[10px] text-slate-400 font-medium line-clamp-1 max-w-[200px]">{product.description || 'No description.'}</div>
                    </div>
                  </div>
                </td>
                <td className="py-4 px-6">
                  <span className="font-mono text-slate-500 font-medium">{product.sku || '-'}</span>
                </td>
                <td className="py-4 px-6 text-slate-800 font-bold">
                  {formatPrice(product.price, product.currency)}
                </td>
                <td className="py-4 px-6">
                  <span className={`px-2 py-0.5 rounded-full border text-[10px] font-bold ${getStockColor(product.stock)}`}>
                    {getStockText(product.stock)}
                  </span>
                </td>
                <td className="py-4 px-6">
                  <span className={`inline-flex items-center w-2 h-2 rounded-full mr-2 ${product.is_active ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                  <span className="text-[11px] font-medium text-slate-500">{product.is_active ? 'Active' : 'Inactive'}</span>
                </td>
                <td className="py-4 px-6 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onEdit(product)}
                      className="text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 border-slate-200 h-8 w-8 p-0 cursor-pointer"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isDeleting}
                      onClick={() => onDelete(product.id)}
                      className="text-slate-400 hover:text-rose-600 hover:bg-rose-50 border-slate-200 hover:border-rose-100 h-8 w-8 p-0 cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
