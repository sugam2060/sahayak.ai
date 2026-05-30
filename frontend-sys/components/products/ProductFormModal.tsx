'use client';

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Checkbox } from '@/components/ui/checkbox';
import { Product } from '@/types/product';
import { Loader2, Upload } from 'lucide-react';
import { toast } from 'sonner';

const formSchema = z.object({
  name: z.string().min(1, 'Product name is required.').max(255),
  description: z.string().optional(),
  price: z.coerce.number().min(0, 'Price must be greater than or equal to 0.'),
  currency: z.string().min(1).default('NPR'),
  stock: z.coerce.number().int().min(0, 'Stock must be greater than or equal to 0.'),
  sku: z.string().max(100).optional().or(z.literal('')),
  image: z.string().max(255).optional().or(z.literal('')),
  is_active: z.boolean().default(true),
});

type FormData = z.infer<typeof formSchema>;

interface ProductFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: Product | null;
  onSubmit: (data: any) => Promise<void>;
  isSubmitting: boolean;
}

export const ProductFormModal = ({ open, onOpenChange, product, onSubmit, isSubmitting }: ProductFormModalProps) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const {
    register,
    handleSubmit,
    setValue,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(formSchema) as any,
    defaultValues: {
      name: '',
      description: '',
      price: 0,
      currency: 'NPR',
      stock: 0,
      sku: '',
      image: '',
      is_active: true,
    },
  });

  useEffect(() => {
    setSelectedFile(null); // Reset file selection whenever product changes
    if (product) {
      reset({
        name: product.name,
        description: product.description || '',
        price: product.price / 100,
        currency: product.currency,
        stock: product.stock,
        sku: product.sku || '',
        image: product.image || '',
        is_active: product.is_active,
      });
    } else {
      reset({
        name: '',
        description: '',
        price: 0,
        currency: 'NPR',
        stock: 0,
        sku: '',
        image: '',
        is_active: true,
      });
    }
  }, [product, reset, open]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleFormSubmit = async (data: FormData) => {
    const formData = new FormData();
    formData.append('name', data.name);
    formData.append('description', data.description || '');
    formData.append('price', Math.round(data.price * 100).toString());
    formData.append('currency', data.currency);
    formData.append('stock', data.stock.toString());
    formData.append('sku', data.sku || '');
    formData.append('is_active', data.is_active ? 'true' : 'false');

    if (selectedFile) {
      formData.append('image_file', selectedFile);
    }

    // If we have an existing product and the image has been cleared (or marked to be cleared)
    if (product && data.image === '') {
      formData.append('clear_image', 'true');
    } else {
      formData.append('clear_image', 'false');
    }
    
    await onSubmit(formData);
    setSelectedFile(null);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-white border border-indigo-50 shadow-2xl rounded-2xl p-6">
        <DialogHeader>
          <DialogTitle className="text-base font-bold text-slate-800">
            {product ? 'Edit Product' : 'Add New Product'}
          </DialogTitle>
          <DialogDescription className="sr-only">
            Fill out the details below to add or edit a product item.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(handleFormSubmit)} className="space-y-4 py-2">
          {/* Product Name */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Product Name</label>
            <Input 
              placeholder="e.g. Wireless Mouse" 
              {...register('name')}
              className="bg-slate-50 border-slate-200 focus:border-indigo-500 rounded-xl"
            />
            {errors.name && <p className="text-[10px] text-rose-500">{errors.name.message}</p>}
          </div>

          {/* Description */}
          <div className="space-y-1">
            <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Description</label>
            <textarea 
              placeholder="Provide a brief description of the product" 
              {...register('description')}
              rows={3}
              className="w-full bg-slate-50 border border-slate-200 focus:border-indigo-500 rounded-xl p-3 text-xs focus:outline-none resize-none"
            />
            {errors.description && <p className="text-[10px] text-rose-500">{errors.description.message}</p>}
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* Price */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Price (NPR)</label>
              <Input 
                type="number" 
                step="0.01"
                placeholder="0.00" 
                {...register('price')}
                className="bg-slate-50 border-slate-200 focus:border-indigo-500 rounded-xl"
              />
              {errors.price && <p className="text-[10px] text-rose-500">{errors.price.message}</p>}
            </div>

            {/* Stock */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Stock Quantity</label>
              <Input 
                type="number" 
                placeholder="0" 
                {...register('stock')}
                className="bg-slate-50 border-slate-200 focus:border-indigo-500 rounded-xl"
              />
              {errors.stock && <p className="text-[10px] text-rose-500">{errors.stock.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {/* SKU */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">SKU Code</label>
              <Input 
                placeholder="e.g. WRLS-MSE-01" 
                {...register('sku')}
                className="bg-slate-50 border-slate-200 focus:border-indigo-500 rounded-xl"
              />
              {errors.sku && <p className="text-[10px] text-rose-500">{errors.sku.message}</p>}
            </div>

            {/* Image File Upload */}
            <div className="space-y-1">
              <label className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Product Image</label>
              <div className="relative">
                <Input 
                  type="file" 
                  accept="image/*"
                  onChange={handleFileChange}
                  className="bg-slate-50 border-slate-200 focus:border-indigo-500 rounded-xl cursor-pointer pt-2 text-xs"
                />
              </div>
              {selectedFile ? (
                <p className="text-[10px] text-indigo-600 font-semibold mt-1 truncate max-w-[180px]" title={selectedFile.name}>Ready to upload: {selectedFile.name}</p>
              ) : product?.image ? (
                <div className="flex items-center justify-between gap-2 mt-1 bg-slate-50 p-1.5 rounded-lg border border-slate-100">
                  <span className="text-[9px] text-slate-400 font-semibold truncate max-w-[170px]">Saved: {product.image}</span>
                  <button 
                    type="button" 
                    onClick={() => {
                      setValue('image', '');
                      toast.info('Image flag removed. Submit form to save.');
                    }}
                    className="text-[9px] text-rose-500 font-bold hover:underline cursor-pointer"
                  >
                    Remove
                  </button>
                </div>
              ) : null}
            </div>
          </div>

          {/* Active status */}
          <div className="flex items-center gap-2 pt-2 select-none">
            <Checkbox 
              id="is_active" 
              defaultChecked={product ? product.is_active : true}
              onCheckedChange={(checked) => setValue('is_active', !!checked)}
            />
            <label htmlFor="is_active" className="text-xs font-bold text-slate-600 cursor-pointer">
              Product is active and visible in catalog
            </label>
          </div>

          <DialogFooter className="pt-4 border-t border-slate-50">
            <Button 
              type="button" 
              variant="outline" 
              onClick={() => onOpenChange(false)}
              className="text-slate-500 border-slate-200 hover:bg-slate-50 rounded-xl text-xs font-semibold cursor-pointer h-10 px-4"
            >
              Cancel
            </Button>
            <Button 
              type="submit" 
              disabled={isSubmitting}
              className="bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-semibold cursor-pointer h-10 px-4 gap-1.5 shadow-sm shadow-indigo-100"
            >
              {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
              {product ? 'Save Changes' : 'Add Product'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
