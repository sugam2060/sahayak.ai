/* eslint-disable @next/next/no-img-element */
'use client';

import React, { useState } from 'react';
import { Package, Trash2, Plus, Minus, Search, ShoppingBag } from 'lucide-react';
import { useProducts } from '@/services/api/products';
import { useCreateOrder, CreateOrderItemInput } from '@/services/api/orders';
import { useSendReply } from '@/services/api/chats';
import { Product } from '@/types/product';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';

interface CreateOrderModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedChat: { platform: string; senderId: number } | null;
}

interface OrderItemState {
  product: Product;
  quantity: number;
}

export const CreateOrderModal = ({ open, onOpenChange, selectedChat }: CreateOrderModalProps) => {
  const [phone, setPhone] = useState('');
  const [address, setAddress] = useState('');
  const [search, setSearch] = useState('');
  const [selectedItems, setSelectedItems] = useState<OrderItemState[]>([]);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [tax, setTax] = useState('0');
  const [deliveryCharge, setDeliveryCharge] = useState('0');

  const createOrderMutation = useCreateOrder();
  const sendReplyMutation = useSendReply();

  // Fetch catalog products
  const { data: productsData } = useProducts({
    limit: 50,
    search: search || undefined,
    is_active: true,
    stock_status: 'in_stock'
  });

  const products = productsData?.products || [];

  const handleAddItem = (product: Product) => {
    setSelectedItems((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        return prev.map((item) =>
          item.product.id === product.id ? { ...item, quantity: item.quantity + 1 } : item
        );
      }
      return [...prev, { product, quantity: 1 }];
    });
  };

  const handleUpdateQuantity = (productId: string, delta: number) => {
    setSelectedItems((prev) =>
      prev
        .map((item) => {
          if (item.product.id === productId) {
            const nextQty = item.quantity + delta;
            return { ...item, quantity: nextQty };
          }
          return item;
        })
        .filter((item) => item.quantity > 0)
    );
  };

  const handleRemoveItem = (productId: string) => {
    setSelectedItems((prev) => prev.filter((item) => item.product.id !== productId));
  };

  const calculateTotal = () => {
    const itemsTotal = selectedItems.reduce((acc, item) => acc + item.product.price * item.quantity, 0);
    const taxPercentage = parseFloat(tax) || 0;
    const taxVal = Math.round(itemsTotal * (taxPercentage / 100));
    const deliveryVal = Math.round((parseFloat(deliveryCharge) || 0) * 100);
    return itemsTotal + taxVal + deliveryVal;
  };

  const handleCreateOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChat) return;
    if (selectedItems.length === 0) {
      setSubmitError('Please add at least one product to the order.');
      return;
    }
    if (!phone.trim()) {
      setSubmitError('Customer phone number is required.');
      return;
    }
    if (phone.trim().length !== 10) {
      setSubmitError('Customer phone number must be exactly 10 digits.');
      return;
    }
    if (!address.trim()) {
      setSubmitError('Delivery address is required.');
      return;
    }

    setSubmitError(null);

    const itemsPayload: CreateOrderItemInput[] = selectedItems.map((item) => ({
      product_id: item.product.id,
      quantity: item.quantity
    }));

    try {
      const res = await createOrderMutation.mutateAsync({
        platform: selectedChat.platform,
        external_customer_id: selectedChat.senderId.toString(),
        customer_phone: phone.trim(),
        delivery_address: address.trim(),
        currency: selectedItems[0]?.product.currency || 'NPR',
        items: itemsPayload,
        tax_percentage: parseInt(tax) || 0,
        delivery_charge: Math.round((parseFloat(deliveryCharge) || 0) * 100)
      });

      if (res.tracking_token) {
        const trackingUrl = `${window.location.origin}/track-your-order/${res.tracking_token}`;
        const trackingMessage = `Your order has been created! Track here: \n ${trackingUrl}`;
        await sendReplyMutation.mutateAsync({
          sender_id: selectedChat.senderId,
          platform: selectedChat.platform,
          text: trackingMessage
        });
      }

      onOpenChange(false);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to create order.');
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[800px] bg-white p-6 rounded-2xl border border-indigo-50 shadow-2xl flex flex-col max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="text-base font-bold text-slate-800 flex items-center gap-2">
            <ShoppingBag className="w-5 h-5 text-indigo-600" />
            Create New Order
          </DialogTitle>
          <DialogDescription className="sr-only">
            Fill in delivery details and select products to create a new order.
          </DialogDescription>
        </DialogHeader>

        {submitError && (
          <div className="p-3 text-xs bg-rose-50 border border-rose-100 rounded-xl text-rose-600 font-medium">
            {submitError}
          </div>
        )}

        <div className="flex gap-6 mt-2 overflow-hidden flex-1 min-h-0">
          {/* Left Panel: Form & Cart */}
          <div className="flex-1 flex flex-col gap-4 overflow-y-auto pr-1">
            <form onSubmit={handleCreateOrder} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Platform</label>
                  <input
                    type="text"
                    disabled
                    value={selectedChat?.platform.toUpperCase() || ''}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-500 font-bold focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Customer ID</label>
                  <input
                    type="text"
                    disabled
                    value={selectedChat?.senderId || ''}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-100 rounded-xl text-xs text-slate-500 font-bold focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Customer Phone</label>
                <input
                  type="text"
                  maxLength={10}
                  placeholder="Enter 10 digit phone number..."
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 focus:border-indigo-500 rounded-xl text-xs focus:outline-none font-medium"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Delivery Address</label>
                <textarea
                  rows={2}
                  placeholder="Enter full shipping/delivery address..."
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 focus:border-indigo-500 rounded-xl text-xs focus:outline-none font-medium resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Tax (%)</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="1"
                    placeholder="0"
                    value={tax}
                    onChange={(e) => setTax(e.target.value)}
                    className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 focus:border-indigo-500 rounded-xl text-xs focus:outline-none font-medium"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1">Delivery Charge (NPR)</label>
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    placeholder="0.00"
                    value={deliveryCharge}
                    onChange={(e) => setDeliveryCharge(e.target.value)}
                    className="w-full px-3 py-1.5 bg-slate-50 border border-slate-200 focus:border-indigo-500 rounded-xl text-xs focus:outline-none font-medium"
                  />
                </div>
              </div>
            </form>

            {/* Selected Items / Cart */}
            <div className="flex-1 flex flex-col min-h-[150px]">
              <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-2">Order Items</h4>
              <div className="flex-1 border border-slate-100 rounded-xl overflow-y-auto p-2 bg-slate-50/50 space-y-2">
                {selectedItems.map((item) => (
                  <div key={item.product.id} className="flex items-center gap-2 bg-white p-2.5 rounded-xl border border-slate-100 shadow-sm">
                    <div className="w-8 h-8 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center overflow-hidden flex-shrink-0">
                      {item.product.image ? (
                        <img src={item.product.image} alt={item.product.name} className="w-full h-full object-cover" />
                      ) : (
                        <Package className="w-4 h-4 text-slate-300" />
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[11px] font-bold text-slate-800 truncate">{item.product.name}</div>
                      <div className="text-[9px] font-semibold text-slate-400 mt-0.5">
                        {new Intl.NumberFormat('en-US', { style: 'currency', currency: item.product.currency }).format(item.product.price / 100)} each
                      </div>
                    </div>

                    {/* Quantity Selector */}
                    <div className="flex items-center gap-1 border border-slate-200 rounded-lg p-0.5 bg-slate-50">
                      <button
                        type="button"
                        onClick={() => handleUpdateQuantity(item.product.id, -1)}
                        className="p-0.5 text-slate-500 hover:bg-white rounded transition-colors cursor-pointer"
                      >
                        <Minus className="w-3 h-3" />
                      </button>
                      <span className="text-[10px] font-bold px-1.5 min-w-[16px] text-center text-slate-700">{item.quantity}</span>
                      <button
                        type="button"
                        onClick={() => handleUpdateQuantity(item.product.id, 1)}
                        className="p-0.5 text-slate-500 hover:bg-white rounded transition-colors cursor-pointer"
                      >
                        <Plus className="w-3 h-3" />
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleRemoveItem(item.product.id)}
                      className="p-1 text-slate-400 hover:text-rose-500 rounded-lg transition-colors cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
                {selectedItems.length === 0 && (
                  <div className="h-full flex items-center justify-center text-center p-6 text-xs text-slate-400">
                    No products added. Select from the catalog list.
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Panel: Catalog Product Selector */}
          <div className="w-[300px] border-l border-slate-100 pl-4 flex flex-col gap-3">
            <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Catalog Products</h4>

            {/* Search */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                placeholder="Search catalog..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-8 pr-3 py-1.5 bg-slate-50 border border-slate-200 focus:border-indigo-500 rounded-xl text-[10px] focus:outline-none font-medium"
              />
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {products.map((p) => (
                <div
                  key={p.id}
                  onClick={() => handleAddItem(p)}
                  className="flex items-center gap-2 p-2 rounded-xl border border-slate-100 hover:border-indigo-100 hover:bg-indigo-50/10 transition-all cursor-pointer"
                >
                  <div className="w-9 h-9 rounded-lg bg-slate-50 border border-slate-100 flex items-center justify-center overflow-hidden flex-shrink-0">
                    {p.image ? (
                      <img src={p.image} alt={p.name} className="w-full h-full object-cover" />
                    ) : (
                      <Package className="w-4 h-4 text-slate-300" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-bold text-slate-800 truncate">{p.name}</div>
                    <div className="text-[8px] font-mono text-slate-400 truncate mt-0.5">{p.sku || 'No SKU'}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] font-bold text-slate-700">
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: p.currency }).format(p.price / 100)}
                    </div>
                    <div className="text-[8px] text-slate-400 mt-0.5">Stock: {p.stock}</div>
                  </div>
                </div>
              ))}
              {products.length === 0 && (
                <div className="text-center py-8 text-[10px] text-slate-400">No products found.</div>
              )}
            </div>
          </div>
        </div>

        {/* Action Footer */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-100 flex-shrink-0 mt-3">
          <div className="text-left">
            <span className="text-[9px] font-bold text-slate-400 uppercase tracking-wider block">Total Amount</span>
            <span className="text-base font-black text-indigo-600">
              {selectedItems.length > 0
                ? new Intl.NumberFormat('en-US', {
                  style: 'currency',
                  currency: selectedItems[0]?.product.currency || 'NPR'
                }).format(calculateTotal() / 100)
                : 'NPR 0.00'}
            </span>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => onOpenChange(false)}
              className="px-4 py-2 text-xs font-bold text-slate-500 hover:text-slate-700 hover:bg-slate-50 rounded-xl transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreateOrder}
              disabled={selectedItems.length === 0 || !phone.trim() || !address.trim() || createOrderMutation.isPending}
              className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl shadow-md shadow-indigo-100 active:scale-[0.98] transition-all cursor-pointer flex items-center gap-1.5"
            >
              {createOrderMutation.isPending ? (
                <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <ShoppingBag className="w-3.5 h-3.5" />
              )}
              Create Order
            </button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
